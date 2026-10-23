"""Compiled intended-failure controls for the typed provider reset phase handoff."""
import os
import shutil
import subprocess

import test_provider_session as parent
from test_host_queue_publication import function


def controls(destination, command, environment):
    variants = (
        ('missing-npu-error-record',
         'session, generation, issued, transport);', 'session, generation, issued, 0);',
         'timeout', 'ambiguous NPU timeout retains ticket and raw transport error after effects'),
        ('missing-mcu-begin-record',
         'npu_rro_reset_mcu_begin(&owner->journal,\n\t\t\t\t\t&owner->plan, session, generation, ticket)',
         'NPU_RRO_OK', 'begin', 'MCU begin matches complete provider and native journals'),
        ('missing-raw-mcu-error',
         'session, generation, ticket, result);', 'session, generation, ticket, 0);',
         'mcu', 'physical MCU raw error remains retained across typed failure'),
    )
    original = (destination/'provider-session.inc').read_text()
    records = []
    env = dict(environment, ASAN_OPTIONS='detect_leaks=0:detect_stack_use_after_return=1:halt_on_error=1')
    for name,before,after,case,diagnostic in variants:
        directory = destination/name
        directory.mkdir()
        for path in destination.iterdir():
            if path.suffix in ('.inc','.c'):
                shutil.copyfile(path,directory/path.name)
        shutil.copytree(destination/'shims',directory/'shims')
        scope = function(original,'airoha_npu_wlan_rro_reset_mcu_complete_session') \
            if name=='missing-raw-mcu-error' else original
        changed_scope = parent.loader.once(scope,before,after)
        changed_source = parent.loader.once(original,scope,changed_scope) if scope!=original else changed_scope
        (directory/'provider-session.inc').write_text(changed_source)
        changed = [str(value).replace(str(destination),str(directory)) for value in command]
        parent.loader.run(changed,directory/'build.log',timeout=300)
        completed = subprocess.run([str(directory/'test'),case],env=env,capture_output=True,text=True,timeout=300)
        (directory/'run.log').write_text(completed.stdout+completed.stderr)
        assert completed.returncode==11 and diagnostic in completed.stderr,(name,completed.returncode,completed.stderr)
        assert 'ERROR: AddressSanitizer' not in completed.stderr and 'runtime error:' not in completed.stderr
        records.append(dict(name=name,compiled=True,assertion_rejected=True,returncode=completed.returncode,
            intended_assertion=diagnostic,sanitizer_fault=False,leak_check=False,
            leak_check_reason='The intended assertion exits before fixture-only disposal.'))
    return records
