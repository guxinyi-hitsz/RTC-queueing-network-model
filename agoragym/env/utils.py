from typing import Optional

from numpy.random import Generator, SeedSequence, PCG64


def RNG(seed: Optional[int] = None):
    if (seed is not None) and not (isinstance(seed, int) and seed >= 0):
        raise Exception("Seed must be a non-negative integer or omitted, not {}".format(seed))

    seed_seq = SeedSequence(seed)
    rng = Generator(PCG64(seed_seq))
    entropy = seed_seq.entropy  # reproducible, SeedSequence(seed_seq.entropy) == seed_seq
    return rng, entropy
