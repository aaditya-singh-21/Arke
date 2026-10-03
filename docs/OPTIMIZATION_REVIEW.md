# Optimization goals and measurement review

**Superseded RAM policy:** this earlier 2026-10-03 review retained a mandatory 1 GiB reserve. The human subsequently accepted [ADR-014](DECISIONS.md#adr-014--advisory-ram-reserve-and-measured-session-stability): that reserve is now advisory, with acceptance based on measured session stability. The original review below is historical rationale, not the current RAM policy. Human/hardware gates remain pending and the runtime/reporting follow-up is now implemented.

2026-10-03. The human asked whether the current benchmarks are the right targets and confirmed closing unnecessary applications and leaving the machine idle for subsequent comparisons.

The documented goals remain appropriate **provisional** targets for this V1: warm median speech-end-to-audible response at most 3 seconds, p95 at most 5 seconds; at least 1 GiB available physical system RAM; at most 3.5 GiB total dedicated VRAM on the 4 GiB device; no crashes/OOM across 30 microphone turns; clean human WER at most 20%; at least 90% human adequacy/intelligibility ratings at least 4/5. They are not promises of conversational quality or universal hardware safety. No target is relaxed by this review.

## What the present experiments can establish

- Fixed inputs, identical source revisions, serial batch one and explicit decoding/placement allow useful diagnostic runtime comparisons. Three warm-ups and three passes over 30 cases yield 90 observations, while cold loading and first inference remain separate.
- File processing through a complete Hindi buffer is relevant to the current synchronous implementation's response cost. It excludes microphone release lag, endpoint timing, playback scheduling and acoustic onset; passing file percentiles is necessary evidence, not a measured microphone response pass. Cold startup is not compared to the warm 3/5-second target.
- Total dedicated device VRAM and available physical system RAM capture hardware headroom. Process RSS includes resident native allocations; private commit records paging pressure but is not resident RAM. PyTorch-only counters and DLL region sizes cannot replace these measurements.
- The 1 GiB RAM and 0.5 GiB VRAM reserves are reasonable initial margins on this small machine. Full-run minima expose load/first-call spikes; steady-state success cannot erase those failures under the current documented gate. The memory gate is not a substitute for the later sustained microphone test.
- Synthetic SAPI speech and unreviewed Hindi drafts exercise deterministic paths and compare outputs. They cannot establish human speech WER, accent/noise coverage, bilingual adequacy, critical details or listening quality. Fingerprint/numerical parity does not replace human review.

## Problem and next comparison

The best all-GPU diagnostic configuration has fast warm file processing and dedicated VRAM below the cap, but measured available RAM has repeatedly failed. Placement/precision changes and per-stage reloads alone have not solved that host margin. CPU cached quantization also failed under changing system load. This does not establish that the models must be replaced.

Background load varied during previous runs. A read-only snapshot during the CPU-only comparison showed Brave resident memory about 764 MiB and Windows nonpaged kernel memory about 1.19 GiB; those values do not identify a leak or exact ownership of all unavailable RAM. Before ASR loading in its one-case probe, after importing PyTorch, only about 463 MiB RAM was available. Comparing such runs cannot isolate causal savings from model/runtime changes.

The next meaningful experiment is a model-free baseline after the current process exits, followed by a fresh run of the strongest unchanged model/precision configuration under the human-confirmed idle desktop. Record baseline and full-run phase headroom together. A repeat distinguishes an isolated success from reproducible headroom. Do not close processes automatically, trim operating-system working sets, hide failed samples, or alter the gate. If the model-free baseline itself lacks 1 GiB, address/understand that baseline before attributing failure to the translator. If clean-baseline runtime still fails, further runtime/weight optimization or an explicitly discussed candidate replacement is justified.

This sequence tests the suspected bottleneck before choosing another model. Human review and microphone validation remain deferred until a viable performance/memory candidate is identified; neither is marked passed.
