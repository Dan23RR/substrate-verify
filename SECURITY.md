# Security

This is a single-author research prototype, not production-hardened. Do not rely on its verdicts as the sole control for a production security decision without your own independent review.

## Scope and honest limits
- A REFUTED verdict ships with an executed counterexample and is sound regardless of the prover.
- A CONFIRMED verdict is execution-backed evidence at the assurance tier stated on the certificate. Bounded-exhaustive is not a universal proof. Read the tier.
- Black-box fuzzing has an open single-point evasion gap (see the README limitations).
- There is no source-to-certificate binding yet: a signature covers the verdict, not a link to the exact source that produced it.

## Reporting a vulnerability or a false certification
Email daniel.culotta@gmail.com with a reproducible case. A particularly welcome report: any on-chain VULN verdict whose exploit reruns to zero or negative profit (a false certification), or any CONFIRMED that a counterexample refutes. These are treated as priority bugs and reported when fixed.
