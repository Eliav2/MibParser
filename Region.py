import re
from typing import Optional, Match


class Region:
    """
    a convenient and efficient extension to re.Match when using with a big immutable string.
    this.should inherit from re.match but re.match is not-extensible so a wrapper was implemented instead.

    just like a regex Match but with option to re-search and narrow down the match
    when searching will always search within the match boundaries.
    (from original text without recreating the string)

    """

    # TODO: i'm not sure: text is being copied each time a Region instance is created?

    def _update_match(self, regText: str = r'(.|\n)*', startBoundary=None, endBoundary=None):
        self.startBoundary = startBoundary if startBoundary else 0
        self.endBoundary = endBoundary if endBoundary else len(self.text)
        self._match: Optional[Match] = re.compile(regText).search(self.text, self.startBoundary, self.endBoundary)
        if self._match:
            self.startBoundary = self._match.start()
            self.endBoundary = self._match.end()

    def __init__(self, text, regText=r'(.|\n)*', startBoundary=None, endBoundary=None):
        self.text = text
        self.region_reg = regText
        self._update_match(regText, startBoundary, endBoundary)

    def search(self, reg=r'(.|\n)*', startBoundary=None, endBoundary=None):
        """ search within region """
        if not self:
            return
        if startBoundary is None:
            startBoundary = self.startBoundary
        if endBoundary is None:
            endBoundary = self.endBoundary
        return Region(self.text, reg, startBoundary, endBoundary)

    def narrow(self, reg):
        """ narrow boundaries and search within boundaries """
        if not self:
            return
        self._update_match(reg, self.startBoundary, self.endBoundary)
        return self

    def finditer(self, regText):
        m = self.search(regText)
        while m:
            yield m
            m = self.search(regText, m.end())

    def start(self):
        return self._match.start()

    def end(self):
        return self._match.end()

    def group(self):
        return self._match.group()

    def __bool__(self):
        return True if self._match else False

    def __repr__(self):
        return self._match.__repr__()

    def __str__(self):
        return self.text[self.startBoundary: self.endBoundary]

    # def __getattr__(self, attr):
    #     try:
    #         return getattr(self._match, attr)
    #     except AttributeError as e:
    #         # re.compile()
    #         if self._match is None:
    #             raise e
    #
    #         def activate_method(*args):
    #             reg = re.compile(args[0])
    #             return getattr(reg, attr)(self.text, self.startBoundary, self.endBoundary)
    #
    #         return activate_method
    # def _compile(self, regText, func):
    #     self._reg = regText
    #     self._reg = re.compile(regText)
    #     # func
    # def split(self, regText):
    #     return self._compile(regText, self._reg.split)
    #
    # def findall(self, regText):
    #     pass


def test():
    demo_text = """
    frxPortTable OBJECT-TYPE
    SYNTAX SEQUENCE OF FrxPortEntry
    ACCESS not-accessible
    STATUS mandatory
    DESCRIPTION
        "This Cisco 90 Series Port Table contains per-port control and
        statistics for each of the subscriber ports in the
        system. The table is indexed first using the Cisco 90 Series
        channel bank digroup number, then by the channel
        unit number (1 to 24), and finally by the port
        number (0-3)."
    ::= { frxPort 1 }
    """

    region = Region(demo_text, r"ACCESS\s+([\w-]+\s+){4}")
    print(region.search(r' mandatory'))  # match
    print(region.search(r'ACCESS'))  # match

    print(region.narrow(r' mandatory'))  # match - now region narrowed
    print(region.narrow(r'ACCESS'))  # None

    region = Region(demo_text, r"ACCESS\s+([\w-]+\s+){4}")

    l = list(region.finditer("a"))
    print(l)


def test_simple():
    s = "my name is verrryyy {Big!} Koko - master of worlds"
    s = "int age=10,size=40"


if __name__ == "__main__":
    test_simple()
    test()
