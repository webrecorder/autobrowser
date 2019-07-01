from typing import Optional, Union, AnyStr

from urlcanon import MatchRule, ParsedUrl, parse_url

URL_T = Union[ParsedUrl, AnyStr]

__all__ = ["StrictMatchRule"]


class StrictMatchRule(MatchRule):
    """This subclass of MatchRule adds strict matching as well as lax matching
    (provided by applies)"""

    def __init__(
        self,
        surt: Optional[AnyStr] = None,
        ssurt: Optional[AnyStr] = None,
        regex: Optional[AnyStr] = None,
        domain: Optional[AnyStr] = None,
        substring: Optional[AnyStr] = None,
        parent_url_regex: Optional[AnyStr] = None,
        url_match: Optional[str] = None,
        value: Optional[str] = None,
        strict: bool = False,
    ) -> None:
        super().__init__(
            surt=surt,
            ssurt=ssurt,
            regex=regex,
            domain=domain,
            substring=substring,
            parent_url_regex=parent_url_regex,
            url_match=url_match,
            value=value,
        )
        self.strict: bool = strict

    def applies(self, url: URL_T, parent_url: Optional[URL_T] = None) -> bool:
        if self.strict:
            return self.applies_strict(url, parent_url)
        return super().applies(url, parent_url)

    def applies_lax(self, url: URL_T, parent_url: Optional[URL_T] = None) -> bool:
        return super().applies(url, parent_url)

    def applies_strict(self, url: URL_T, parent_url: Optional[URL_T] = None) -> bool:
        """Returns true if the supplied URL matches this rules exactly.

        If the rules was created with a 'domain' supplied the host of the supplied
        URL must match the configured 'domain' exactly, likewise with 'surt' and 'ssurt'.

        :param url: The URL to be tested to determine if it matches against this rules
        :param parent_url: parent url, should be supplied if the rule has a
        `parent_url_regex`
        :return: T/F indicating if the supplied URL matches this rule
        """
        if not isinstance(url, ParsedUrl):
            url = parse_url(url)
        if self.domain and self.domain != url.host:
            return False
        if self.surt and url.surt() != self.surt:
            return False
        if self.ssurt and url.ssurt() != self.ssurt:
            return False
        if self.substring and url.__bytes__().find(self.substring) == -1:
            return False
        if self.regex:
            if not self.regex.match(url.__bytes__()):
                return False
        if self.parent_url_regex:
            if not parent_url:
                return False
            if isinstance(parent_url, ParsedUrl):
                parent_url = parent_url.__bytes__()
            elif isinstance(parent_url, str):
                parent_url = parent_url.encode("utf-8")
            if not self.parent_url_regex.match(parent_url):
                return False
        return True
