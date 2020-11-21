"""
.. autoclass:: Type

.. autoclass:: Casing
    :members:

.. autoclass:: TurkicCasing
.. autoclass:: GermanCasing
"""

from enum import Enum
from typing import Tuple, List, Iterator


Type = Enum('Type', 'NO INIT ALL HUHINIT HUH')
"""
Type of capitalization, detected by :meth:`Casing.guess`:

* ``NO``: all lowercase ("foo")
* ``INIT``: titlecase, only initial letter is capitalized ("Foo")
* ``ALL``: all uppercase ("FOO")
* ``HUH``: mixed capitalization ("fooBar")
* ``HUHINIT``: mixed capitalization, first letter is capitalized ("FooBar")
"""


class Casing:
    """
    Represents casing-related algorithms specific for dictionary's language. It is class, not a set
    of functions, because it needs to have subclasses for specific language casing, which have only
    some aspects different from generic one.
    """

    def guess(self, word: str, *,                      # pylint: disable=no-self-use
              for_corrections: bool = False) -> Type:  # pylint: disable=unused-argument
        """
        Guess word's capitalization. Redefined in :class:`GermanCasing` (and ``for_corrections``
        argument relevant only there).
        """

        if word.islower():
            return Type.NO
        if word.isupper():
            return Type.ALL
        if word[:1].isupper():
            return Type.INIT if word[1:].islower() else Type.HUHINIT
        return Type.HUH

    def lower(self, word) -> List[str]:  # pylint: disable=no-self-use
        """
        Lowercases the word. It returns *list* of possible lowercasings for all casing classes to
        behave consistently. In :class:`GermanCasing` (and only there), lowercasing word like
        "STRASSE" produces two possibilities: "strasse" and "straße" (ß is most of the time upcased
        to SS, so we can't decide which of downcased words is "right" and need to check both).

        Redefined also in :class:`TurkicCasing`, because in Turkic languages lowercase
        "i" is uppercased as "İ", and uppercae "I" is downcased as "ı".
        """

        # can't be properly lowercased in non-Turkic collaction
        if not word or word[0] == 'İ':
            return []

        # turkic "lowercase dot i" to latinic "i", just in case
        return [word.lower().replace('i̇', 'i')]

    def upper(self, word) -> str:   # pylint: disable=no-self-use
        """
        Uppercase the word. Redefined in :class:`TurkicCasing`, because in Turkic languages lowercase
        "i" is uppercased as "İ", and uppercae "I" is downcased as "ı".
        """
        return word.upper()

    def capitalize(self, word) -> Iterator[str]:
        """
        Capitalize (convert word to all lowercase and first letter uppercase). Returns a list of
        results for same reasons as :meth:`lower`
        """
        return (self.upper(word[0]) + lower for lower in self.lower(word[1:]))

    def lowerfirst(self, word) -> Iterator[str]:
        """
        Just change the case of the first letter to lower. Returns a list of
        results for same reasons as :meth:`lower`
        """
        return (letter + word[1:] for letter in self.lower(word[0]))

    def variants(self, word: str) -> Tuple[Type, List[str]]:
        """
        Returns hypotheses of how the word might have been cased (in dictionary), if we consider it is
        spelled correctly. E.g., if the word is "Kitten", hypotheses are "kitten", "Kitten".
        """
        captype = self.guess(word)

        if captype == Type.NO:
            result = [word]
        elif captype == Type.INIT:
            result = [word, *self.lower(word)]
        elif captype == Type.HUHINIT:
            result = [word, *self.lowerfirst(word)]
        elif captype == Type.HUH:
            result = [word]
        elif captype == Type.ALL:
            result = [word, *self.lower(word), *self.capitalize(word)]

        return (captype, result)

    def corrections(self, word: str) -> Tuple[Type, List[str]]:
        """
        Returns hyphotheses of how the word might have been cased if it is a misspelling. For example,
        the word "DiCtionary" (HUHINIT capitalization) produces hypotheses "DiCtionary" (itself),
        "diCtionary", "dictionary", "Dictionary", and all of them are checked by Suggest.
        """

        captype = self.guess(word, for_corrections=True)

        if captype == Type.NO:
            result = [word]
        elif captype == Type.INIT:
            result = [word, *self.lower(word)]
        elif captype == Type.HUHINIT:
            result = [word, *self.lowerfirst(word), *self.lower(word), *self.capitalize(word)]
            # TODO: also here and below, consider the theory FooBar meant Foo Bar
        elif captype == Type.HUH:
            result = [word, *self.lower(word)]
        elif captype == Type.ALL:
            result = [word, *self.lower(word), *self.capitalize(word)]

        return (captype, result)

    def coerce(self, word: str, cap: Type) -> str:
        """
        Used by suggest: by known (valid) suggestion, and initial word's capitalization, produce
        proper suggestion capitalization. E.g. if the misspelling was "Kiten" (INIT capitalization),
        found suggestion "kitten", then this method makes it "Kitten".
        """
        if cap in (Type.INIT, Type.HUHINIT):
            return self.upper(word[0]) + word[1:]
        if cap == Type.ALL:
            return self.upper(word)
        return word


class TurkicCasing(Casing):
    """
    Redefines :meth:`Casing.upper` and :meth:`Casing.lower`, because in Turkic languages lowercase
    "i" is uppercased as "İ", and uppercae "I" is downcased as "ı"::

        >>> turkic = spyll.hunspell.algo.capitalization.TurkicCasing()
        >>> turkic.lower('Izmir'))
        ['ızmir']
        >>> turkic.upper('Izmir')
        IZMİR

    """

    U2L = str.maketrans('İI', 'iı')
    L2U = str.maketrans('iı', 'İI')

    def lower(self, word):
        return super().lower(word.translate(self.U2L))

    def upper(self, word):
        return super().upper(word.translate(self.L2U))


class GermanCasing(Casing):
    """
    Redefines :meth:`Casing.lower` because in German "SS" can be lowercased both as "ss" and "ß"::

        >>> german = spyll.hunspell.algo.capitalization.GermanCasing()
        >>> german.lower('STRASSE'))
        ['straße', 'strasse']
    """

    def lower(self, word):
        def sharp_s_variants(text, start=0):
            pos = text.find('ss', start)
            if pos == -1:
                return []
            replaced = text[:pos] + 'ß' + text[pos+2:]
            return [replaced, *sharp_s_variants(replaced, pos+1), *sharp_s_variants(text, pos+2)]

        lowered = super().lower(word)[0]

        if 'SS' in word:
            return [*sharp_s_variants(lowered), lowered]

        return [lowered]

    def guess(self, word, *, for_corrections=False):
        result = super().guess(word)
        # if for_corrections and 'ß' in word and super().guess(word.replace('ß', '')) == Type.ALL:
        if 'ß' in word and super().guess(word.replace('ß', '')) == Type.ALL:
            return Type.ALL
        return result
