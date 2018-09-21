from typing import Dict

import pytest
from _pytest.fixtures import SubRequest
import uvloop
from ruamel.yaml import YAML
from pathlib import Path


@pytest.yield_fixture()
def event_loop():
    loop = uvloop.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def behavior_manager_config(request: SubRequest) -> Dict:
    yaml = YAML()
    with (Path(__file__).parent / "autobrowser" / "behaviors" / "behaviors.yaml").open(
        "r"
    ) as iin:
        config = yaml.load(iin)
    if request.cls:
        request.cls.config = config
    return config
