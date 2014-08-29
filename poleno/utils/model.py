# vim: expandtab
# -*- coding: utf-8 -*-

from django.db import models
from django.shortcuts import get_object_or_404

from misc import Bunch

class FieldChoices(object):
    u"""
    Simple container for django model field choices following DRY principle.

    Example:
        class Mail(models.Model):
            STATUSES = FieldChoices(
                (UNKNOWN, 1, _(u'Unknown')),
                (DELIVERED, 2, _(u'Delivered')),
                (RETURNED, 3, _(u'Returned')),
                (LOST, 4, _(u'Lost')),
                )
            status = models.SmallIntegerField(choices=STATUSES._choices, verbose_name=_(u'Status'))

        mail = Mail()
        mail.status = mail.STATUSES.DELIVERED
    """

    def __init__(self, *args):
        choices = []
        inverse = {}
        for choice_name, choice_key, choice_value in args:
            if isinstance(choice_value, (list, tuple)): # It's a choice group
                group = []
                bunch = Bunch()
                for group_name, group_key, group_value in choice_value:
                    group.append((group_key, group_value))
                    inverse[group_key] = u'%s__%s' % (choice_name, group_name)
                    bunch.__dict__[group_name] = group_key
                choices.append((choice_key, group))
                inverse[choice_key] = choice_name
                self.__dict__[choice_name] = bunch
            else:
                choices.append((choice_key, choice_value))
                inverse[choice_key] = choice_name
                self.__dict__[choice_name] = choice_key
        self._choices = choices
        self._inverse = inverse

class QuerySet(models.query.QuerySet):
    u"""
    Wrapper to simplify adding custom query methods for defined models. For every model you can
    inherit this ``QuerySet`` and add your query methods. This class defines several handy shortcut
    methods as well. The new methods work for models, as well as for forward and backward
    relations.

    Example:

        class ArticleQuerySet(QuerySet):
            def published(self):
                return self.filter(published=True)
            def popular(self):
                return self.filter(popular=True)

        class Author(Model):
            name = models.CharField(...)

        class Article(Model):
            author = models.ForeignKey(Author, ...)
            published = BooleanField(...)
            popular = BooleanField(...)

            objects = ArticleQuerySet.as_manager()

        Article.objects.published().popular()
        Author.objects.get(...).article_set.published()

    Source:
        http://adam.gomaa.us/blog/2009/feb/16/subclassing-django-querysets/index.html
        http://stackoverflow.com/questions/4576622/in-django-can-you-add-a-method-to-querysets#answer-7961021

    In contrast to the sources, we create new ``QuerySetManager`` class dynamically for every
    model. Otherwise Django wouldn't be able to inherit from it properly and dynamically create
    ``RelatedManager`` for forward and backward realtions.
    """

    @classmethod
    def as_manager(cls):

        class QuerySetManager(models.Manager):
            use_for_related_fields = True

            def get_query_set(self):
                return cls(self.model)

            def __getattr__(self, name, *args):
                if name.startswith(u'_'):
                    raise AttributeError
                return getattr(self.get_query_set(), name, *args)

        return QuerySetManager()

    def get_or_404(self, *args, **kwargs):
        u"""
        Uses ``get()`` to return an object, or raises a ``Http404`` exception if the object does
        not exist. Like with ``get()``, an ``MultipleObjectsReturned`` will be raised if more than
        one object is found.
        """
        return get_object_or_404(self, *args, **kwargs)
