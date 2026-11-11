from .text_matcher import TextMatcher


class ExactMatcher(TextMatcher):
    def matches(self, a, b) -> bool:
        return self.normalise(a) == self.normalise(b)
