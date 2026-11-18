#!/usr/bin/env python3
"""Verify the staged PPE ownership patch without writing the prepared kernel."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shlex
import shutil
import struct
import subprocess
from tempfile import TemporaryDirectory

from elftools.elf.elffile import ELFFile

from verify_consumer_queue_owner import ROOT, digest, function, ordered, require
from verify_ppe_stop import BUILD, PAIR, PRISTINE, instruction, rv32

HERE = Path(__file__).resolve().parent
CHECKPOINTS = ROOT / "research/checkpoints"
CHECKPOINT = CHECKPOINTS / "2026-11-18-npu-ppe-table-owner"
PATCH = CHECKPOINT / "airoha-ppe-table-owner.patch"
ETH = Path("drivers/net/ethernet/airoha")
INPUTS = {
    "airoha_eth.c": "8b884862cbfce17d0e515334a90f143aad549819dbdc6c7d5f9e8baae5ac9517",
    "airoha_eth.h": "385ee3d772b3483c62fc4072b833d802f1fab5eb982abeda3949f22738eb153b",
    "airoha_ppe.c": "476ccc884f0a66ae35ffa2b8535d587fe9b697b0654877b8a9c114615def6f03",
}
CONFIG = "e6fee1dd3dd98757e104798fd4c8301a752d01ce9604e2583683b0586adcc4e3"
KERNEL_CMD = {
    "airoha_eth": "3aef3fed96915ac87830ca0607832a90dedb14c8d3064ed1802281ab9bc9d7e4",
    "airoha_ppe": "d0d1c792311038aff4a71f43851d59e7b9f3d44d32b05c7006725fcfa1bb540b",
}
COMPILER_SHA = "7f770a9b898c9c2ffce1bea614e10a520d0ee55f2dfcc3b6d9a35d9da76e06d4"
EXTRACT = [
    "airoha_ppe_dma_exposed", "airoha_ppe_free_unexposed", "airoha_ppe_release_dma",
    "airoha_ppe_prepare_dma", "airoha_ppe_alloc_table", "airoha_ppe_publish_dma",
    "airoha_ppe_flush_sram_entries", "airoha_ppe_stop_npu", "airoha_ppe_offload_setup",
    "airoha_ppe_setup_tc_block_cb", "airoha_ppe_deinit",
]


def run(argv, **kwargs):
    result = subprocess.run(argv, timeout=45, text=True, capture_output=True, **kwargs)
    require(result.returncode == 0,
            f"{Path(argv[0]).name} failed: {(result.stderr or result.stdout).strip()[-2000:]}")
    return result


def verify_config(kernel):
    config = kernel / ".config"
    require(digest(config) == CONFIG and
            "# CONFIG_NET_AIROHA_FLOW_STATS is not set" in config.read_text().splitlines(),
            "not the pinned stats-disabled kernel config")
    provider = kernel / ETH / "airoha_npu.c"
    require(digest(provider) == "52f729bee29743d17c7235755e5b561b4cb107ec7cd4a08ad1ecc08106cd5768",
            "not the exact mailbox sender")
    source = provider.read_text()
    enum, = re.findall(r"enum \{([^{}]*\bPPE_FUNC_SET_WAIT_FLOW_STATS_SETUP[^{}]*)\};", source)
    entries = [name.strip() for name in enum.split(",") if name.strip()]
    require(entries.index("PPE_FUNC_SET_WAIT_FLOW_STATS_SETUP") == 4, "stats selector drift")
    sender = function(source, "airoha_npu_ppe_stats_setup")
    require(ordered(sender, "ppe_data->func_type=NPU_OP_SET;",
                    "ppe_data->func_id=PPE_FUNC_SET_WAIT_FLOW_STATS_SETUP;",
                    "ppe_data->stats_info.foe_stats_addr=foe_stats_addr;", "airoha_npu_send_msg(",
                    "if(err)gotoout;", "npu->stats=devm_ioremap(", "if(!npu->stats)err=-ENOMEM;"),
            "stats setup ordering drift")

    stop_receipt = CHECKPOINTS / "2026-11-18-npu-ppe-stop/EVIDENCE.json"
    firmware = json.loads(stop_receipt.read_bytes())["firmware"]
    code, data = (PAIR / name for name in ("CODE.bin", "DATA.bin"))
    original_code = PRISTINE / "en7581_MT7996_npu_rv32.bin"
    original_data = PRISTINE / "en7581_MT7996_npu_data.bin"
    require(all(digest(p) == firmware["inputs"][str(p.relative_to(ROOT))]
                for p in (code, data, original_code, original_data)), "firmware bytes changed")
    require(struct.unpack_from("<I", data.read_bytes(), 0x13C) == (0x84005DF2,) and
            data.read_bytes()[0x13C:0x140] == original_data.read_bytes()[0x13C:0x140] and
            code.read_bytes()[0x5DF2:0x5DF6] == original_code.read_bytes()[0x5DF2:0x5DF6],
            "initial stats dispatch differs")
    decoded = rv32(code, (0x84005DF2, 0x84005DF6))
    instruction(decoded, 0x84005DF2, "c.li", "a0,0")
    instruction(decoded, 0x84005DF4, "c.jr", "ra")
    return dict(config_sha256=CONFIG, stats_enabled=False, stats_selector=4,
                initial_stats_slot="0x3e90013c", initial_stats_stub="0x84005df2",
                stats_stub_return=0, code_sha256=digest(code), data_sha256=digest(data))


def apply_patch(kernel, work):
    for name, sha in INPUTS.items():
        original = kernel / ETH / name
        require(digest(original) == sha, f"prepared source drift: {name}")
        (work / ETH).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, work / ETH / name)
    argv = ["git", "apply", "--whitespace=error-all"]
    stat = run([*argv, "--numstat", "-z", PATCH], cwd=work).stdout
    paths = [part.split("\t", 2)[-1] for part in stat.split("\0") if part]
    require(sorted(paths) == sorted(str(ETH / name) for name in INPUTS), "patch scope differs")
    result = run(["patch", "--batch", "--forward", "--no-backup-if-mismatch",
                  "--fuzz=0", "-p1", "-i", PATCH], cwd=work)
    require(not re.search(r"\b(offset|fuzz|FAILED)\b", result.stdout + result.stderr),
            "patch needed an offset or did not apply")


def inspect_sources(work):
    eth = (work / ETH / "airoha_eth.c").read_text()
    ppe = (work / ETH / "airoha_ppe.c").read_text()
    require(ordered(function(eth, "airoha_probe"), "eth->dev=&pdev->dev;",
                    "err=airoha_ppe_prepare_dma(eth);if(err)returndev_err_probe(",
                    "dma_set_mask_and_coherent(", "devm_platform_ioremap_resource_byname(",
                    "airoha_hw_init("), "owner guard does not precede register and reset access")
    init = function(ppe, "airoha_ppe_init")
    require(ordered(init, "ppe->foe=airoha_ppe_alloc_table(ppe,foe_size,false);",
                    "if(!ppe->foe)return-ENOMEM;", "if(ppe_num_stats_entries>0){",
                    "ppe->foe_stats=airoha_ppe_alloc_table(ppe,foe_size,true);",
                    "if(!ppe->foe_stats)return-ENOMEM;",
                    "err=airoha_ppe_flush_sram_entries(ppe);if(err)returnerr;"),
            "PPE allocation or SRAM failure order differs")
    require(function(ppe, "airoha_ppe_hw_init").count("REG_PPE_TB_BASE(") == 1 and
            "for(i=0;i<eth->soc->num_ppe;i++){airoha_fe_wr(eth,REG_PPE_TB_BASE(i),"
            "ppe->foe_dma+sram_tb_size);" in function(ppe, "airoha_ppe_hw_init") and
            len(re.findall(r"\bREG_PPE_TB_BASE\(", ppe + eth)) == 1 and
            len(re.findall(r"\bairoha_ppe_hw_init\(", ppe + eth)) == 2 and
            len(re.findall(r"->ops\.ppe_init_stats\(", ppe + eth)) == 1 and
            len(re.findall(r"\bdmam_alloc_coherent\(", ppe)) == 1,
            "unexpected alternate PPE table allocation or publication")
    return ppe


def extract(ppe):
    declarations = [re.search(r"^struct " + name + r" \{\n.*?^\};", ppe, re.S | re.M)
                    for name in ("airoha_ppe_dma_buf", "airoha_ppe_dma_owner")]
    global_owner = re.search(r"^static struct airoha_ppe_dma_owner \*w1700k_ppe_owner;$", ppe, re.M)
    require(global_owner and all(declarations), "owner definitions missing")
    bodies = []
    for name in EXTRACT:
        start = re.search(r"^[^\n]*\b" + name + r"\([^;{}]*?\)\n\{", ppe, re.M)
        require(start, "missing case implementation: " + name)
        bodies.append(ppe[start.start():ppe.index("\n}", start.end()) + 2])
    return "\n\n".join([*(match[0] for match in declarations), global_owner[0], *bodies]) + "\n"


def native(work, extracted):
    include = work / "ppe-table-owner-under-test.inc"
    binary = work / "ppe-table-owner-harness"

    def compile_run(code, succeeds):
        include.write_text(code, encoding="ascii")
        run(["cc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-sign-compare",
             "-I", work, HERE / "ppe-table-owner-harness.c", "-o", binary], cwd=work)
        result = subprocess.run([binary], cwd=work, timeout=10, capture_output=True, text=True,
                                env=dict(os.environ, LC_ALL="C"))
        if succeeds:
            require(result.returncode == 0 and result.stdout.strip() == "9 PPE table owner cases passed",
                    "native cases failed: " + result.stderr)
        else:
            require(result.returncode == -6 and "Assertion" in result.stderr,
                    "compiled negative control did not fail an assertion")

    compile_run(extracted, True)
    controls = [
        ("free-exposed", "if (buf->va && !buf->exposed)", "if (buf->va)"),
        ("allow-rebind", "if (w1700k_ppe_owner) {", "if (false && w1700k_ppe_owner) {"),
        ("ignore-module-refusal", "&& !try_module_get(THIS_MODULE))",
         "&& !try_module_get(THIS_MODULE) && false)"),
        ("retry-partial-publication", "if (owner && airoha_ppe_dma_exposed(owner))\n\t\treturn",
         "if (false && owner && airoha_ppe_dma_exposed(owner))\n\t\treturn"),
        ("leave-offload-open-on-deinit", "clear_bit(DEV_STATE_REGISTERED, &eth->state);", ""),
    ]
    for name, old, new in controls:
        require(extracted.count(old) == 1, "ambiguous fault injection: " + name)
        compile_run(extracted.replace(old, new, 1), False)
    return dict(cases=9, mutated_assertions=[row[0] for row in controls],
                extracted_sha256=hashlib.sha256(extracted.encode("ascii")).hexdigest())


def cross(kernel, work):
    compiler, = BUILD.glob("staging_dir/toolchain-*/bin/aarch64-openwrt-linux-musl-gcc")
    require(digest(compiler) == COMPILER_SHA, "unexpected compiler")
    outputs = {}
    for stem, sha in KERNEL_CMD.items():
        obj, source = ETH / (stem + ".o"), ETH / (stem + ".c")
        command = (kernel / ETH / ("." + obj.name + ".cmd")).read_bytes().splitlines(keepends=True)[0]
        require(hashlib.sha256(command).hexdigest() == sha, "saved kernel compile command drift")
        dep = "-Wp,-MMD," + str(ETH / ("." + obj.name + ".d"))
        argv = shlex.split(command.decode().split(":=", 1)[1])
        require(argv[:3] == ["ccache", compiler.name, dep] and
                argv[-4:] == ["-c", "-o", str(obj), str(source)],
                "unrecognized compile command")
        dest = work / obj
        run(["nice", "-n", "19", "prlimit", "--as=402653184", "--", compiler, *argv[3:-4],
             "-iquote", kernel / ETH, "-ffile-prefix-map=" + str(work) + "=.ppe-table-owner-check",
             "-c", "-o", dest, work / source], cwd=kernel)
        with dest.open("rb") as stream:
            elf = ELFFile(stream)
            require(elf.little_endian and elf.elfclass == 64 and elf["e_machine"] == "EM_AARCH64"
                    and elf["e_type"] == "ET_REL", "unexpected compiler output")
            prepare, = elf.get_section_by_name(".symtab").get_symbol_by_name("airoha_ppe_prepare_dma")
            require((prepare["st_shndx"] == "SHN_UNDEF") == (stem == "airoha_eth"),
                    "missing Ethernet probe/owner linkage")
            outputs[stem] = dict(sha256=digest(dest), command_sha256=sha,
                                 text_sha256=hashlib.sha256(elf.get_section_by_name(".text").data()).hexdigest())
    return dict(objects=outputs, compiler_sha256=COMPILER_SHA, address_space_limit_bytes=402653184)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cross", action="store_true", help="compile two isolated AArch64 objects")
    parser.add_argument("--check", action="store_true", help="compare the checked scope with the saved receipt")
    args = parser.parse_args()
    kernel, = BUILD.glob("build_dir/target-*/linux-airoha*/linux-6.18.52")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with TemporaryDirectory(prefix="npu-ppe-owner-") as tmp:
        work = Path(tmp)
        apply_patch(kernel, work)
        pre = verify_config(kernel)
        owner = inspect_sources(work)
        result = dict(schema="w1700k-ppe-table-owner-v1", original=INPUTS,
                      patched={name: digest(work / ETH / name) for name in INPUTS},
                      patch_sha256=digest(PATCH), baseline_configuration=pre,
                      native=native(work, extract(owner)), linked_module=False,
                      board_run=False, physical_retirement_proven=False)
        if args.cross:
            result["cross_compile"] = cross(kernel, work)
    if args.check:
        expected = json.loads((CHECKPOINT / "EVIDENCE.json").read_bytes())
        if not args.cross:
            expected.pop("cross_compile")
        require(result == expected, "result differs from the saved PPE owner receipt")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
