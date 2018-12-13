import pytest
from autobrowser.behaviors.scroll import AutoScrollBehavior, ScrollBehavior
from autobrowser.behaviors.timeline_feeds import TimelineFeedBehavior, TimelineFeedNetIdle
from autobrowser.behaviors.behavior_manager import (
    create_default_behavior_man,
    BehaviorManager,
    load_behavior_class,
)


@pytest.mark.parametrize(
    "loadable,expected",
    [
        ({"module": "scroll", "class": "AutoScrollBehavior"}, AutoScrollBehavior),
        ({"module": "scroll", "class": "ScrollBehavior"}, ScrollBehavior),
        (
            {"module": "autobrowser.behaviors.scroll", "class": "AutoScrollBehavior"},
            AutoScrollBehavior,
        ),
        (
            {"module": "autobrowser.behaviors.scroll", "class": "ScrollBehavior"},
            ScrollBehavior,
        ),
    ],
)
def test_load_behavior_class(loadable, expected):
    assert load_behavior_class(loadable) == expected


@pytest.mark.usefixtures("behavior_manager_config")
class TestBehaviorManger(object):
    def test_was_created(self):
        assert BehaviorManager is not None
        assert len(BehaviorManager.matchers) > 0 and len(BehaviorManager.matchers) == len(
            self.config["matching"]
        )
        assert len(BehaviorManager.default_behavior_init) == 2
        assert BehaviorManager.default_behavior_init[0] == load_behavior_class(
            self.config["default"]["handler"]
        )

    def test_create_default_returns_same_as_default(self):
        new_instance = create_default_behavior_man()
        assert len(BehaviorManager.matchers) == len(new_instance.matchers)
        assert len(BehaviorManager.default_behavior_init) == len(
            new_instance.default_behavior_init
        )

        for created, new in zip(BehaviorManager.matchers, new_instance.matchers):
            assert created.behavior_class == new.behavior_class
            assert created.behavior_config == new.behavior_config
            assert repr(created.matcher) == repr(new.matcher)

    @pytest.mark.parametrize(
        "url, expected, resource",
        [
            ("https://twitter.com/webrecorder_io", TimelineFeedNetIdle, 'twitterTimeline.js'),
            ("https://facebook.com", TimelineFeedBehavior, 'facebookNewsFeed.js'),
            ("https://facebook.com/abc", TimelineFeedBehavior, 'facebookUserFeed.js'),
            ("", AutoScrollBehavior, 'autoscroll.js'),
        ],
    )
    def test_matches_behavior_to_url(self, url, expected, resource):
        behavior = BehaviorManager.behavior_for_url(url, "")
        assert isinstance(behavior, expected)
        assert behavior.conf.get('resource') == resource
