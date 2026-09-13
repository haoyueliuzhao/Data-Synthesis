# Read-only linear verification and supervised handoff

## Scope and existing state

This is a new operational implementation, developed on
`codex/linear-postprocess-20260913` from main commit
`fcb0607b81709479285e30f4e42a8e9f53094647`. It does not change the historical
source, tests, collection, financial qualification, material-selection,
budget, training, decoder, or evaluation rules. It does not belong to the
independent anchored-VTDO branch. No main-arm or confirmation results were
read for this work.

The original collection has a sealed manifest and a complete fixed-collection
report for all 24,640 registered sessions. The existing follower, PID 726630,
was observed repeatedly reading the sealed collection manifest; the material
and Student output directories had not been created. Those are observations,
not permanent state assumptions: every handoff must inspect them again.

The original Parent implementation rehashes the entire manifest for each
member read. The sealed manifest is 84,035,934 bytes with 408,398 members, so
one repeated-manifest sweep reads approximately 34.32 TB of manifest bytes.
Observed process read progress indicated approximately 8–9 hours per such
sweep, with more than one full-parent verification in the existing pipeline.
This is an observed I/O bottleneck, not evidence of a deadlock or an estimate
of Student training duration.

## Preserved contract

`LinearParent` is a subclass of the original Parent. For unchanged, valid,
fully declared regular-file inputs it returns the same `bytes`, `read`,
`descriptor`, and `verify_all` results. Every member is still read and checked
against its original SHA-256 and exact size. No member content is cached or
skipped. Original records, IDs, source surfaces, and private references are
not rewritten.

The manifest is pinned with an `O_NOFOLLOW` descriptor, checked by full SHA at
construction and at both full-verification boundaries, and checked by pinned
descriptor and namespace metadata on every read. Directory traversal uses
directory-relative descriptors, rejects symlinks and special files, and
requires exactly the declared files and their necessary directories. A final
metadata sweep detects changes in previously read members. These are stricter
acceptance checks: undeclared extra files, empty directories and namespace
changes are refused, even if the original reader might have ignored them.

Linux inotify watches the pinned manifest, member inodes, and directories.
This detects same-clock-tick modifications and changes made via outside
hardlinks, which timestamp comparisons alone do not reliably detect.
Unexpected notifications, lost watches, malformed events, queue overflow,
initialization failure, read failure, and capacity exhaustion fail closed.
There is no stat-only fallback and no system-limit modification. A shared
monitor de-duplicates watches among concurrently live parents; owner references
are released when a parent closes or is finalized. Only the exact expected
pure `IN_IGNORED` event from a successful explicit watch removal is consumed as
cleanup; mixed or unrelated events remain fatal.

This is not an atomic filesystem snapshot. It assumes sealed, local Linux
inputs and no writer. Inotify does not comprehensively report pre-existing
writable mmap or direct-storage/kernel mutation. The supervisor checks managed
processes and requires an explicit operator assurance about other writers.
An additional same-UID inspection reported no visible writable collection FDs
or mappings among 26 processes, but four system/sshd processes did not permit
mapping inspection. This is explicitly limited visibility, not a proof that
every process on the host is incapable of writing.

## Narrow process-local integration

`adapter.installed` changes only the explicitly enumerated Parent aliases in
nine existing supervisor modules. Qualification, financial parsing, package
selection, budget, training, decoding, and assessment functions retain their
original objects. The aliases and record factory are restored on success or
failure. The only record-factory addition is
`postprocessing_verification_adapter` in the future Student `study_freeze`.
That field binds the source registration, new source/test/document hashes,
old follower lineage, original collection parent, reviewed plan and explicit
authorization. New source files must appear in the original freeze's real
code snapshot. Other original record kinds retain byte-identical rendering.

Original model workers remain fresh subprocesses. They do not inherit these
in-memory aliases. Public generation inputs are not expanded to include
materials or private reference data. The original training material reader
and low-level loss/kernel assertions remain unchanged.

The new runner invokes the original `basis_student.stage.advance` once after
the handoff gates, then retains the original publication behavior. It does not
start a collector. The original complete-collection → one materialization →
original N decision → A training/dev/selection → B confirmation pipeline is
reused. If original material qualification ends below N=180, that remains an
accepted terminal outcome, with no prefix selection, replenishment or retry.
Original available-GPU checks remain authoritative; no GPU availability is
assumed from development-time observations.

## Required handoff sequence

Development tests and read-only preflight do **not** authorize stopping a
process or starting materialization or models.

1. Finish review and tests, commit only the new operational files, and
   fast-forward the operational branch onto main. Do not merge anchored-VTDO.
2. On main, register the final committed source. Every historical scoped file
   must match the baseline Git blob; all new source, controls, documentation
   and preflight evidence must match their committed bytes. The execution
   data root must equal the loaded code root, and the branch must be main.
3. Save a fresh reviewed inspection while exactly the identified old follower
   is still alive. Match PID, UID, start ticks and command digest to the
   follower-start lineage. Require no collector, other writer-capable
   supervisor, Student worker, partial material/Student output, or old
   failure/completion record.
4. Obtain explicit reviewed operator approval tied to the exact source
   registration and plan IDs and limited no-other-writer assurance. Recheck
   the old process identity immediately before a pidfd-based operator stop.
   Save the authorization's `verified_stopped_process_identity` from that
   verified PID/UID/start-tick/command identity, not a guessed PID. Do not claim
   the process has stopped before that has actually been checked. This module
   never sends signals or attaches to a process.
5. After the old follower has stopped, invoke the single new `execute` entry.
   It rechecks unchanged collection/follower lineage, absence of all conflicting
   managed processes and outputs, and the one-time operation directory. It
   saves the handoff identity before invoking the original pipeline.
6. A failed attempt retains its receipts and any partial outputs and does not
   automatically retry. A successful attempt records only terminal IDs in the
   operational report; scientific results remain in their original outputs.

Only unfinished repeated read-only hash work is abandoned at the handoff.
No collected session, sealed manifest, material package or model is deleted.
Source registration and the installed adapter binding remain fixed during the
run, even when the original publisher later advances main with artifact commits.

## Validation evidence and limits

The original 68 synthetic manifest tests and the original 150 basis-Student
controls passed together: **218 passed in 58.68 seconds**, exit 0, in the
isolated operational worktree. These CPU tests did not start models or inspect
real qualification/confirmation outcomes. The final new-package regression
separately passed **172 tests in 3.09 seconds** (an independent repeated run
passed in 3.10 seconds): 77 manifest controls, 18 adapter/metadata controls,
and 77 supervisor gates. Ruff passed for the full new package and its tests.
These final counts include owner cleanup, late-cleanup mutation, process
identity and option-order conflict detection controls. They are not represented
as part of the earlier historical 218 count.

A permitted, read-only full check of the actual sealed collection passed in
**76.12612745608203 seconds**. It checked all 408,398 members, 143,891 required
directories and 5,557,955,937 member bytes, with 552,299 watched inodes and
three full manifest hashes. This observed approximately 34 TB repeated-manifest
work becoming 252,107,802 manifest bytes plus the same member reads. It is not
a measured end-to-end training speedup. The machine's watch limit was 1,048,576;
future concurrently live parents remain subject to a fail-closed limit.

The preflight ran before the subsequent owner-lifecycle cleanup and final
supervisor gates; its exact implementation was uncommitted and no code digest
was recorded by that diagnostic. Accordingly, it establishes compatibility
with this sealed file set and the core full verification, not a claim that the
later final code commit was independently executed against production data.
See `preflight_evidence.json` for the explicitly bounded observation. No
scientific output was written, no old process was stopped, and no production
materialization or model execution occurred during the preflight.

After all implementation changes, a second explicitly permitted read-only
preflight ran from **2026-09-13 10:57:03 to 10:58:24 Asia/Shanghai**. All five
final source-file SHA-256 values were recorded before verification and matched
again at exit. The same sealed collection passed in **78.8493423468899 seconds**,
followed by **2.2910583880729973 seconds** of owner cleanup. All 408,398 members
and 143,891 directories were checked again with the same full-hash and byte
counts. Both the monitor's owner map and the actual kernel inotify FD reported
**0 watches after cleanup**, down from 552,299. No notification failure occurred;
the monitor closed and the diagnostic exited 0. The nested
`final_implementation_preflight` entry records this final source-bound evidence
separately from the earlier unbound observation. It still does not itself
authorize a handoff, and did not stop the old follower, write scientific
artifacts, materialize packages or invoke any model.
