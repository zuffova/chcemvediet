# vim: expandtab
# -*- coding: utf-8 -*-
import random

class Bunch(object):
    u"""
    Simple object with defened attributes.

    Source: http://code.activestate.com/recipes/52308-the-simple-but-handy-collector-of-a-bunch-of-named/

    Example:
        b = Bunch(key=value)
        b.key
        b.other = value
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def random_readable_string(length, vowels=u'aeiouy', consonants=u'bcdfghjklmnprstvxz'):
    u"""
    Returns a random string ``length`` characters long of the following form. Every string is
    generated with equal probability.

    [:vowel:]? ([:consonant:][:vowel:])* [:consonant:]?

    Where `[:vowel:]` is the set of all vowels `[aeiouy]` and `['consonant']` is the set of
    consonants `[bcdfghjklmnprstvxz]`. Use can use ``vowels`` and ``consonants`` arguments to set
    your own sets of vowels and consonants.
    """
    res = []
    if random.random() < len(vowels) / float(len(vowels) + len(consonants)):
        res.append(random.choice(vowels))
    while len(res) < length:
        res.append(random.choice(consonants))
        if len(res) < length:
            res.append(random.choice(vowels))
    return u''.join(res)
