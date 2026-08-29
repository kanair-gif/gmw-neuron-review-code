# Control-theoretic workspace core experiment

This package tests whether a small dynamical subnetwork can be recovered as a Global Workspace-like core from controllability and observability.

## Main idea

The original external-access score asks whether inputs at a candidate cluster can control the rest of the network and whether observations at that cluster can reconstruct the rest. The synthetic test reveals a failure mode: a set containing disconnected actuator-only and observer-only nodes can score highly.

The proposed correction treats the candidate cluster itself as a dynamical mediator. With the partition

```text
x_S(t+1) = A_SS x_S(t) + A_SR x_R(t)
y_R(t)   = A_RS x_S(t)
```

it computes finite-horizon controllability and observability Gramians inside `S`, obtains an internal mediation singular-value spectrum, and defines

```text
WMS(S) = sum(eta_i) * effective_rank(eta)/|S| * module_globality(S)
```

where `eta_i` are the mediation singular values.

## Reproduce

Download and extract `gmw-neuron-review-code-20260830.zip`, then run:

```bash
python workspace_core_experiment.py --output-dir results
```

Full run, including 12 repeated beam searches and exact enumeration of all 635,376 four-node clusters:

```bash
python workspace_core_experiment.py --output-dir results --full
```

Dependencies: Python 3.10+, NumPy, pandas, and Matplotlib.
