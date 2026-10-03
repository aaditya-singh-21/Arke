import pytest
from voice_translator.metrics import MemorySampler, RAM_ADVISORY_BYTES, VRAM_LIMIT_BYTES


def sample(ram, gpu, time=1.):
    return {'time': time, 'rss': 100, 'private': 200, 'vms': 200,
            'ram_total': 8 * 1024**3, 'ram_available': ram, 'gpu_used': gpu}


@pytest.mark.parametrize('ram,advisory', [(0, 'warning'), (75 * 1024**2, 'warning'),
                                        (RAM_ADVISORY_BYTES - 1, 'warning'), (RAM_ADVISORY_BYTES, 'ok')])
def test_ram_is_advisory_even_at_zero(ram, advisory):
    memory = MemorySampler()
    memory.samples = [sample(ram, VRAM_LIMIT_BYTES)]
    report = memory.summary()
    assert report['memory_gate'] == report['vram_gate'] == 'pass'
    assert report['ram_advisory'] == advisory
    assert report['telemetry_status'] == 'complete'
    assert report['minimum_available_ram_bytes'] == ram
    assert report['memory_policy'] == 'adr-014-ram-advisory'


def test_vram_still_blocks_with_abundant_ram():
    memory = MemorySampler()
    memory.samples = [sample(4 * 1024**3, VRAM_LIMIT_BYTES + 1)]
    assert memory.summary()['memory_gate'] == 'fail'


@pytest.mark.parametrize('condition', ['empty', 'missing_ram', 'missing_gpu', 'gpu_gap', 'error'])
def test_incomplete_telemetry_never_passes(condition):
    memory = MemorySampler()
    if condition != 'empty':
        memory.samples = [sample(RAM_ADVISORY_BYTES, 0)]
    if condition == 'missing_ram': memory.samples[0]['ram_available'] = None
    if condition == 'missing_gpu': memory.samples[0]['gpu_used'] = None
    if condition == 'gpu_gap': memory.samples.append(sample(RAM_ADVISORY_BYTES, None, 2.))
    if condition == 'error': memory.errors.add('GPU query failed')
    assert memory.summary()['memory_gate'] == 'unverified'
    assert memory.summary()['telemetry_status'] == 'unverified'
