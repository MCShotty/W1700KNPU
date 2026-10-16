# Original API24 RRO Effects

This is direct original-instruction evidence with explicit synthetic RAM,not
checked-current-pair admission,fresh initialization,physical DMA,concurrent
reset or reclamation proof. The live tail caller/fault inputs are unchanged.
Constructor selectors2/7 do not close the separate RRO selectors0/1/3 contract.

## Exact Inputs And Executed Cases

The original CODE/DATA hashes are e743d1b5/61a75afb,not the changed raw19-component
pair. The saved Ghidra export is independently rehashed to
098da31821148eddb15d68d5d0c7b9cb889c03a5f2e1282f0b31e33aafbebcb9;
no new Ghidra reanalysis is claimed. Its wrapper8400fc2c loads24 bytes and calls
8400e084;the wrapper returns1 regardless of the inner routine's status.

`test_inode_rro_original.py` executes137 direct callback probes with24-byte
packets:all128 element blocks,one separate session table,five reset boundaries
(0,7,8,1023,1024),and three additional address-alias inputs. Original clear
helper840103aa executes normally for selector0. No helper result is substituted;
the model's printf/hart stubs are not reached by these cases.

A host compiler evaluates the exact current MT7996 header macros/record
declaration:1024 sessions,1024 entries/session,128 blocks,eight sessions/block,
8192 entries/block and eight-byte records. These are current source dimensions,
not physical allocation/backing witnesses.

| Selector | Original Effect | Exact Data Footprint Per Call |
| --- | --- | --- |
| 0 | Publish one pointer at3e901fdc+4*block;clear64KiB;set byte7 of all8192 records toff | 65540 bytes/24577 stores |
| 1 | Publish session-table pointer at3e90458c;set byte7 of1024 records toff,leaving other bytes unchanged | 1028 bytes/1025 stores |
| 3 | Set one session's1024 signature bytes toff;IDs0..1023 choose block=id/8 and slot=id%8;ID1024 chooses the separate session table | 1024 bytes/1024 stores |

Original pointer conversion is `(physical & 0x3fffffff) | 0x40000000`. Tests map
that computed alias as synthetic RAM. Accepting this mathematical alias does not
prove a real PMA/cache/coherent mapping. The oracle's index/alias bounds are not
new bounds checks in the stock callback.

Every intended data byte must actually be written,including writes that leave
an already-correct value unchanged. Whole32KiB SRAM and the complete synthetic
alias image must match an independent pre-state projection;all other writes
are confined to a bounded original stack frame. Distinct S0-S11/TP,GP/SP and
MSTATUS are checked across return,and original CODE remains byte-identical.

Receipt `.local/npu-inode-rro-original/rro-q2/result.json`, SHA256
`2d01b092cebe1e91530ec4a426c8f6421b7a0d4e3e2dbe788b5a6e20168cc540`.
The earlierq1 driver/receipt remains preserved with its initial-register ABI
limitation;it is not promoted as the distinctive-registerq2 execution. Five
synthetic projection controls and all172 selected units pass independently.

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu:tools \
  python3 -B tests/npu/test_inode_rro_original.py --name fresh-name
```

## Current Source And Remaining Ownership

Current mt76_npu_send_txrx_addr returns its error. In current mt7996/init.c,
the selector0 element publication,selector1 session publication and selector3
work-item reset are bare calls without checking that returned value. This is
source observation,not a newly executed physical or actual-C failure result.
Do not infer that all error state is otherwise invisible to the provider.

Before admitting these commands,bind actual retained host allocations,full
extents/record geometry,session/boot/endpoint identities and exact permitted
publication/reset order. Cover host caller error propagation,partial
publication,timeout/late callbacks and session generations. Resetting signature
bytes is not a worker/DMA drain,and callback return1 is not an initialization
witness. Full RRO/BA/free-pool/refill/packet fate and actual-client behavior
remain open. No current RV32 guard,checked dispatch,production C,source lock,
firmware image,router state or calibration was changed for these probes.
