"""Bind a staged Ethernet source delta and linked module to a FIT seal."""
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import tempfile

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from npu_replay_proof import SOURCE_LOCK, digest, is_digest, path_under, read_pinned, require
import verify_merged_image as fit_tools

ETH_MODULE = "airoha-eth.ko"
ETH_DRIVER = Path("drivers/net/ethernet/airoha")
ETH_SOURCES = ("airoha_eth.c", "airoha_eth.h", "airoha_ppe.c")
PPE = "9999-w1700k-ppe-table-owner.patch"
QDMA = "9999-w1700k-qdma-owner.patch"
BUNDLES = ".local/npu-coherent-handoff-20261118/bundles"
BUILD = ".build/merged-openwrt"
BUILD_CONFIG = "firmware/build.config"
KERNELS = Path("build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581")
MAX_MODULE = 8 << 20


def required_patches(lock):
    minor = lock["kernel"].rsplit(".", 1)[0]
    names = {row["path"]: row["sha256"] for row in lock.get("openwrt", {}).get("changed_files", [])}
    prefix = f"target/linux/airoha/patches-{minor}/"
    selected = {prefix + name: names[prefix + name] for name in (PPE, QDMA) if prefix + name in names}
    require(prefix + QDMA not in selected or prefix + PPE in selected,
            "The QDMA patch requires the staged PPE preimage")
    return selected


def verify_bundle(root, world, patches, bundle_path, pin):
    path = path_under(root / BUNDLES, root / bundle_path)
    require(path.name == "receipt.json" and path.parent.parent == root / BUNDLES,
            "Expected a staged Ethernet source bundle receipt")
    bundle, bundle_pin = read_pinned(path, pin)
    require(bundle["schema"] == 1 and bundle["source_preflight_passed"] is True and
            bundle["source_delta_only"] is True and bundle["linux_modules_built"] is False and
            bundle["fit_built"] is False and bundle["board_contact"] is False,
            "Not a verified source-only Ethernet bundle")
    files = bundle["files"]
    require(files[SOURCE_LOCK] == world["source_lock_sha256"] and
            bundle["prepared_overlay_staging"]["source_lock_sha256"] == world["source_lock_sha256"] and
            bundle["parent_lock_sha256"] != world["source_lock_sha256"] and
            {p: files.get(f"firmware/overlay/openwrt/{p}") for p in patches} == patches,
            "Ethernet bundle does not match the world source lock")
    for name, expected in files.items():
        relative = PurePosixPath(name)
        require(relative.as_posix() == name and not relative.is_absolute() and
                ".." not in relative.parts and "\\" not in name and
                (name == SOURCE_LOCK or relative.is_relative_to("firmware/overlay/openwrt")) and
                is_digest(expected) and world["declarations"].get(name) == expected and
                digest(path_under(world["frozen"], name)) == expected,
                f"World capsule does not bind Ethernet bundle member: {name}")
    stack = bundle["source_stack"]["kernel"]
    names = [Path(p).name for p in patches]
    require([p for p in stack["patch_order"] if p in (PPE, QDMA)] == names,
            "Wrong staged Ethernet patch sequence")
    return bundle_pin, stack["postimages"], names


def inspect_linked(raw, release, *, with_qdma=False, require_owner=True):
    try:
        elf = ELFFile(io.BytesIO(raw))
    except ELFError as error:
        raise ValueError("Malformed linked Ethernet ELF module") from error
    require(elf.little_endian and elf.elfclass == 64 and
            elf["e_machine"] == "EM_AARCH64" and elf["e_type"] == "ET_REL",
            "Expected an AArch64 relocatable kernel module")
    info = elf.get_section_by_name(".modinfo")
    table = elf.get_section_by_name(".symtab")
    index = elf.get_section_index(".gnu.linkonce.this_module")
    require(info is not None and table is not None and index is not None,
            "Linked Ethernet module lacks Kbuild module metadata")
    instance = table.get_symbol_by_name("__this_module") or []
    require(len(instance) == 1 and instance[0]["st_shndx"] == index and
            instance[0]["st_info"]["type"] == "STT_OBJECT" and
            0 < instance[0]["st_size"] <= elf.get_section(index)["sh_size"],
            "Linked Ethernet module lacks a defined module instance")
    tags = info.data().split(b"\0")

    def field(key):
        key += b"="
        values = [tag[len(key):] for tag in tags if tag.startswith(key)]
        require(len(values) == 1, f"Expected one Ethernet module {key.decode()} field")
        return values[0].decode("ascii")

    vermagic, name = field(b"vermagic"), field(b"name")
    depends = field(b"depends").split(",")
    require(vermagic == f"{release} SMP mod_unload aarch64" and name == "airoha_eth" and
            field(b"intree") == "Y" and "airoha_npu" in depends and
            b"alias=of:N*T*Cairoha,en7581-eth" in tags, "Wrong Ethernet module identity or kernel ABI")
    definitions = ["init_module", "cleanup_module"]
    if require_owner:
        definitions.append("airoha_ppe_prepare_dma")
        if with_qdma:
            definitions.append("airoha_qdma_release_owner")
    for symbol in definitions:
        rows = table.get_symbol_by_name(symbol) or []
        require(len(rows) == 1 and isinstance(rows[0]["st_shndx"], int) and
                rows[0]["st_info"]["type"] == "STT_FUNC",
                f"Linked Ethernet module lacks definition: {symbol}")
    return dict(name=name, vermagic=vermagic, depends=depends, definitions=definitions)


def normalization_tool(root, world):
    provenance = world["image"]["packaged_module_provenance"]
    require(provenance["profile"] == "openwrt-w1700k-no-rename-no-build-id" and
            provenance["objcopy_args"] == list(fit_tools.KMOD_OBJCOPY_ARGS),
            "Unsupported Ethernet module packaging profile")
    frozen = path_under(world["frozen"], BUILD_CONFIG)
    config = digest(frozen)
    require(config == world["declarations"].get(BUILD_CONFIG) == provenance["config_sha256"],
            "Ethernet strip profile was not bound to the frozen build config")
    versions = re.findall(r'^CONFIG_GCC_VERSION="([0-9]+(?:\.[0-9]+)+)"$', frozen.read_text(), re.M)
    require(len(versions) == 1, "Missing selected OpenWrt compiler version")
    relative = f"staging_dir/toolchain-aarch64_cortex-a53_gcc-{versions[0]}_musl/bin/aarch64-openwrt-linux-musl-objcopy"
    tool_pin = provenance["objcopy_sha256"]
    require(provenance["objcopy"] == relative and is_digest(tool_pin), "Unbound Ethernet strip tool")
    return path_under(root / BUILD, relative), tool_pin, config


def normalize(raw, tool, tool_pin, scratch):
    require(is_digest(tool_pin) and digest(tool) == tool_pin, "Ethernet strip tool digest mismatch")
    with tempfile.TemporaryDirectory(prefix="ethernet-strip-", dir=scratch) as directory:
        src, dst = (Path(directory) / name for name in ("linked.ko", "packaged.ko"))
        src.write_bytes(raw)
        fit_tools.run([tool, *fit_tools.KMOD_OBJCOPY_ARGS, src, dst])
        require(dst.is_file() and 0 < dst.stat().st_size <= MAX_MODULE,
                "Missing or oversized normalized Ethernet module")
        expected = digest(dst)
    require(digest(tool) == tool_pin, "Ethernet strip tool changed during verification")
    return expected


def bind_linked(root, world, options, scratch):
    patches = required_patches(world["source_lock"])
    bundle = getattr(options, "ethernet_bundle", None)
    bundle_pin = getattr(options, "ethernet_bundle_sha256", None)
    module_pin = getattr(options, "ethernet_linked_sha256", None)
    if not patches:
        require(bundle is bundle_pin is module_pin is None,
                "Ethernet proof is only for a staged Ethernet source lock")
        return None
    require(bundle is not None and is_digest(bundle_pin) and is_digest(module_pin),
            "This source lock requires a pinned Ethernet bundle and linked module")

    bundle_pin, postimages, names = verify_bundle(root, world, patches, bundle, bundle_pin)
    kernel = KERNELS / f"linux-{world['kernel']}"
    directory = world["build_upper"]
    sources = {}
    for name in ETH_SOURCES:
        inner = (ETH_DRIVER / name).as_posix()
        path = path_under(directory, kernel / inner)
        pin = digest(path)
        require(pin == postimages.get(inner), f"Prepared Ethernet source differs from staged postimage: {name}")
        sources[inner] = pin
    rel = kernel / ETH_DRIVER / ETH_MODULE
    linked = path_under(directory, rel)
    with linked.open("rb") as stream:
        raw = stream.read(MAX_MODULE + 1)
    require(0 < len(raw) <= MAX_MODULE and hashlib.sha256(raw).hexdigest() == module_pin,
            "Linked Ethernet module digest or size differs from the independent pin")
    metadata = inspect_linked(raw, world["kernel"], with_qdma=QDMA in names)
    tool, tool_pin, config = normalization_tool(root, world)
    packaged = normalize(raw, tool, tool_pin, scratch)
    require(digest(path_under(directory, rel)) == module_pin and all(
            digest(path_under(directory, kernel / name)) == pin for name, pin in sources.items()),
            "Ethernet build outputs changed while binding the image")
    return dict(bundle_sha256=bundle_pin, source_lock_sha256=world["source_lock_sha256"],
                patch_order=names, prepared_sources=sources, linked=rel.as_posix(),
                linked_sha256=module_pin, linked_bytes=len(raw), metadata=metadata,
                config_sha256=config, objcopy_sha256=tool_pin, expected_packaged_sha256=packaged)
