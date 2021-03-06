# vim: expandtab
# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from django import forms
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import smart_text
from django.utils.functional import lazy
from multiselectfield import MultiSelectFormField

from poleno.attachments.forms import AttachmentsField
from poleno.utils.models import after_saved
from poleno.utils.forms import AutoSuppressedSelect, PrefixedForm
from poleno.utils.misc import squeeze
from poleno.utils.date import local_today
from chcemvediet.apps.obligees.forms import ObligeeWithAddressInput, ObligeeAutocompleteField
from chcemvediet.apps.inforequests.models import Branch, Action


class ActionAbstractForm(PrefixedForm):
    branch = forms.TypedChoiceField(
            label=_(u'inforequests:ActionAbstractForm:branch:label'),
            empty_value=None,
            widget=AutoSuppressedSelect(
                attrs={
                    u'class': u'with-tooltip span5',
                    u'data-toggle': u'tooltip',
                    u'data-placement': u'right',
                    u'title': lazy(render_to_string, unicode)(u'inforequests/modals/tooltips/branch-field.txt'),
                    },
                suppressed_attrs={
                    u'class': u'suppressed-control',
                    }),
            )

    def __init__(self, *args, **kwargs):
        self.inforequest = kwargs.pop(u'inforequest')
        self.draft = kwargs.pop(u'draft', False)
        super(ActionAbstractForm, self).__init__(*args, **kwargs)

        # Assumes that converting a Branch to a string gives its ``pk``
        field = self.fields[u'branch']
        field.choices = [(branch, branch.historicalobligee.name)
                for branch in self.inforequest.branches
                    if branch.can_add_action(self.action_type)]
        if len(field.choices) > 1:
            field.choices = [(u'', u'')] + field.choices

        def coerce(val):
            for o, v in field.choices:
                if o and smart_text(o.pk) == val:
                    return o
            raise ValueError # pragma: no cover
        field.coerce = coerce

        if self.draft:
            self.fields[u'branch'].required = False

    def save(self, action):
        assert self.is_valid()
        action.branch = self.cleaned_data[u'branch']

    def save_to_draft(self, draft):
        assert self.is_valid()
        draft.branch = self.cleaned_data[u'branch']

    def load_from_draft(self, draft):
        self.initial[u'branch'] = draft.branch

class EffectiveDateMixin(ActionAbstractForm):
    effective_date = forms.DateField(
            label=_(u'inforequests:EffectiveDateMixin:effective_date:label'),
            localize=True,
            widget=forms.DateInput(attrs={
                u'placeholder': _('inforequests:EffectiveDateMixin:effective_date:placeholder'),
                u'class': u'datepicker with-tooltip',
                u'data-toggle': u'tooltip',
                u'data-placement': u'right',
                u'title': lazy(render_to_string, unicode)(u'inforequests/modals/tooltips/effective_date-field.txt'),
                }),
            )

    def __init__(self, *args, **kwargs):
        super(EffectiveDateMixin, self).__init__(*args, **kwargs)
        if self.draft:
            self.fields[u'effective_date'].required = False

    def clean(self):
        cleaned_data = super(EffectiveDateMixin, self).clean()

        if not self.draft:
            branch = cleaned_data.get(u'branch', None)
            effective_date = cleaned_data.get(u'effective_date', None)
            if effective_date:
                try:
                    if branch and effective_date < branch.last_action.effective_date:
                        raise ValidationError(_(u'inforequests:EffectiveDateMixin:older_than_previous_error'))
                    if effective_date > local_today():
                        raise ValidationError(_(u'inforequests:EffectiveDateMixin:from_future_error'))
                    if effective_date < local_today() - relativedelta(months=1):
                        raise ValidationError(_(u'inforequests:EffectiveDateMixin:older_than_month_error'))
                except ValidationError as e:
                    self.add_error(u'effective_date', e)

        return cleaned_data

    def save(self, action):
        super(EffectiveDateMixin, self).save(action)
        action.effective_date = self.cleaned_data[u'effective_date']

    def save_to_draft(self, draft):
        super(EffectiveDateMixin, self).save_to_draft(draft)
        draft.effective_date = self.cleaned_data[u'effective_date']

    def load_from_draft(self, draft):
        super(EffectiveDateMixin, self).load_from_draft(draft)
        self.initial[u'effective_date'] = draft.effective_date

class FileNumberMixin(ActionAbstractForm):
    file_number = forms.CharField(
            label=_(u'inforequests:FileNumberMixin:file_number:label'),
            max_length=255,
            required=False,
            widget=forms.TextInput(attrs={
                u'placeholder': _(u'inforequests:FileNumberMixin:file_number:placeholder'),
                u'class': u'span5',
                }),
            )

    def save(self, action):
        super(FileNumberMixin, self).save(action)
        action.file_number = self.cleaned_data[u'file_number']

    def save_to_draft(self, draft):
        super(FileNumberMixin, self).save_to_draft(draft)
        draft.file_number = self.cleaned_data[u'file_number']

    def load_from_draft(self, draft):
        super(FileNumberMixin, self).load_from_draft(draft)
        self.initial[u'file_number'] = draft.file_number

class SubjectContentMixin(ActionAbstractForm):
    subject = forms.CharField(
            label=_(u'inforequests:SubjectContentMixin:subject:label'),
            max_length=255,
            widget=forms.TextInput(attrs={
                u'placeholder': _(u'inforequests:SubjectContentMixin:subject:placeholder'),
                u'class': u'span5',
                }),
            )
    content = forms.CharField(
            label=_(u'inforequests:SubjectContentMixin:content:label'),
            widget=forms.Textarea(attrs={
                u'placeholder': _(u'inforequests:SubjectContentMixin:content:placeholder'),
                u'class': u'input-block-level',
                }),
            )

    def __init__(self, *args, **kwargs):
        super(SubjectContentMixin, self).__init__(*args, **kwargs)
        if self.draft:
            self.fields[u'subject'].required = False
            self.fields[u'content'].required = False

    def save(self, action):
        super(SubjectContentMixin, self).save(action)
        action.subject = self.cleaned_data[u'subject']
        action.content = self.cleaned_data[u'content']

    def save_to_draft(self, draft):
        super(SubjectContentMixin, self).save_to_draft(draft)
        draft.subject = self.cleaned_data[u'subject']
        draft.content = self.cleaned_data[u'content']

    def load_from_draft(self, draft):
        super(SubjectContentMixin, self).load_from_draft(draft)
        self.initial[u'subject'] = draft.subject
        self.initial[u'content'] = draft.content

class AttachmentsMixin(ActionAbstractForm):
    attachments = AttachmentsField(
            label=_(u'inforequests:AttachmentsMixin:attachments:label'),
            required=False,
            upload_url_func=(lambda: reverse(u'inforequests:upload_attachment')),
            download_url_func=(lambda a: reverse(u'inforequests:download_attachment', args=(a.pk,))),
            )

    def __init__(self, *args, **kwargs):
        self.attached_to = kwargs.pop(u'attached_to')
        super(AttachmentsMixin, self).__init__(*args, **kwargs)

        self.fields[u'attachments'].attached_to = self.attached_to

    def save(self, action):
        super(AttachmentsMixin, self).save(action)

        @after_saved(action)
        def deferred(action):
            action.attachment_set = self.cleaned_data[u'attachments']

    def save_to_draft(self, draft):
        super(AttachmentsMixin, self).save_to_draft(draft)

        @after_saved(draft)
        def deferred(draft):
            draft.attachment_set = self.cleaned_data[u'attachments']

    def load_from_draft(self, draft):
        super(AttachmentsMixin, self).load_from_draft(draft)
        self.initial[u'attachments'] = draft.attachments

class DeadlineMixin(ActionAbstractForm):
    deadline = forms.IntegerField(
            label=_(u'inforequests:DeadlineMixin:deadline:label'),
            initial=Action.DEFAULT_DEADLINES.EXTENSION,
            min_value=2,
            max_value=100,
            widget=forms.NumberInput(attrs={
                u'placeholder': _(u'inforequests:DeadlineMixin:deadline:placeholder'),
                u'class': u'with-tooltip',
                u'data-toggle': u'tooltip',
                u'data-placement': u'right',
                u'title': lazy(render_to_string, unicode)(u'inforequests/modals/tooltips/deadline-field.txt'),
                }),
            )

    def __init__(self, *args, **kwargs):
        super(DeadlineMixin, self).__init__(*args, **kwargs)
        if self.draft:
            self.fields[u'deadline'].required = False

    def save(self, action):
        super(DeadlineMixin, self).save(action)
        action.deadline = self.cleaned_data[u'deadline']

    def save_to_draft(self, draft):
        super(DeadlineMixin, self).save_to_draft(draft)
        draft.deadline = self.cleaned_data[u'deadline']

    def load_from_draft(self, draft):
        super(DeadlineMixin, self).load_from_draft(draft)
        self.initial[u'deadline'] = draft.deadline

class AdvancedToMixin(ActionAbstractForm):
    advanced_to_1 = ObligeeAutocompleteField(
            label=_(u'inforequests:AdvancedToMixin:advanced_to_1:label'),
            widget=ObligeeWithAddressInput(attrs={
                u'placeholder': _(u'inforequests:AdvancedToMixin:advanced_to_1:placeholder'),
                u'class': u'with-tooltip span5',
                u'data-toggle': u'tooltip',
                u'data-placement': u'right',
                u'data-container': u'.modal.in',
                u'title': lazy(render_to_string, unicode)(u'inforequests/modals/tooltips/advanced_to-field.txt'),
                }),
            )
    advanced_to_2 = ObligeeAutocompleteField(
            label=_(u'inforequests:AdvancedToMixin:advanced_to_2:label'),
            required=False,
            widget=ObligeeWithAddressInput(attrs={
                u'placeholder': _(u'inforequests:AdvancedToMixin:advanced_to_2:placeholder'),
                u'class': u'with-tooltip span5',
                u'data-toggle': u'tooltip',
                u'data-placement': u'right',
                u'data-container': u'.modal.in',
                u'title': lazy(render_to_string, unicode)(u'inforequests/modals/tooltips/advanced_to-field.txt'),
                }),
            )
    advanced_to_3 = ObligeeAutocompleteField(
            label=_(u'inforequests:AdvancedToMixin:advanced_to_3:label'),
            required=False,
            widget=ObligeeWithAddressInput(attrs={
                u'placeholder': _(u'inforequests:AdvancedToMixin:advanced_to_3:placeholder'),
                u'class': u'with-tooltip span5',
                u'data-toggle': u'tooltip',
                u'data-placement': u'right',
                u'data-container': u'.modal.in',
                u'title': lazy(render_to_string, unicode)(u'inforequests/modals/tooltips/advanced_to-field.txt'),
                }),
            )
    ADVANCED_TO_FIELDS = [u'advanced_to_1', u'advanced_to_2', u'advanced_to_3']

    def __init__(self, *args, **kwargs):
        super(AdvancedToMixin, self).__init__(*args, **kwargs)
        if self.draft:
            for field in self.ADVANCED_TO_FIELDS:
                self.fields[field].required = False

    def clean(self):
        cleaned_data = super(AdvancedToMixin, self).clean()

        if not self.draft:
            branch = cleaned_data.get(u'branch', None)
            for i, field in enumerate(self.ADVANCED_TO_FIELDS):
                advanced_to = cleaned_data.get(field, None)
                if advanced_to:
                    try:
                        if branch and advanced_to.pk == branch.obligee_id:
                            raise ValidationError(_(u'inforequests:AdvancedToMixin:same_obligee_error'))
                        for field_2 in self.ADVANCED_TO_FIELDS[0:i]:
                            advanced_to_2 = cleaned_data.get(field_2, None)
                            if advanced_to_2 == advanced_to:
                                raise ValidationError(_(u'inforequests:AdvancedToMixin:duplicate_obligee_error'))
                    except ValidationError as e:
                        self.add_error(field, e)

        return cleaned_data

    def save(self, action):
        super(AdvancedToMixin, self).save(action)

        @after_saved(action)
        def deferred(action):
            for field in self.ADVANCED_TO_FIELDS:
                obligee = self.cleaned_data[field]
                if obligee:
                    sub_branch = Branch(
                            obligee=obligee,
                            inforequest=action.branch.inforequest,
                            advanced_by=action,
                            )
                    sub_branch.save()

                    sub_action = Action(
                            branch=sub_branch,
                            effective_date=action.effective_date,
                            type=Action.TYPES.ADVANCED_REQUEST,
                            )
                    sub_action.save()

    def save_to_draft(self, draft):
        super(AdvancedToMixin, self).save_to_draft(draft)

        @after_saved(draft)
        def deferred(draft):
            draft.obligee_set = [self.cleaned_data[f]
                    for f in self.ADVANCED_TO_FIELDS
                    if self.cleaned_data[f]]

    def load_from_draft(self, draft):
        super(AdvancedToMixin, self).load_from_draft(draft)
        for field, obligee in zip(self.ADVANCED_TO_FIELDS, draft.obligees):
            self.initial[field] = obligee

class DisclosureLevelMixin(ActionAbstractForm):
    disclosure_level = forms.TypedChoiceField(
            label=_(u'inforequests:DisclosureLevelMixin:disclosure_level:label'),
            choices=[(u'', u'')] + Action.DISCLOSURE_LEVELS._choices,
            coerce=int,
            empty_value=None,
            widget=forms.Select(attrs={
                u'class': u'with-tooltip',
                u'data-toggle': u'tooltip',
                u'data-placement': u'right',
                u'title': lazy(render_to_string, unicode)(u'inforequests/modals/tooltips/disclosure_level-field.txt'),
                }),
            )

    def __init__(self, *args, **kwargs):
        super(DisclosureLevelMixin, self).__init__(*args, **kwargs)
        if self.draft:
            self.fields[u'disclosure_level'].required = False

    def save(self, action):
        super(DisclosureLevelMixin, self).save(action)
        action.disclosure_level = self.cleaned_data[u'disclosure_level']

    def save_to_draft(self, draft):
        super(DisclosureLevelMixin, self).save_to_draft(draft)
        draft.disclosure_level = self.cleaned_data[u'disclosure_level']

    def load_from_draft(self, draft):
        super(DisclosureLevelMixin, self).load_from_draft(draft)
        self.initial[u'disclosure_level'] = draft.disclosure_level

class RefusalReasonMixin(ActionAbstractForm):
    refusal_reason = MultiSelectFormField(
            label=_(u'inforequests:RefusalReasonMixin:refusal_reason:label'),
            choices=Action.REFUSAL_REASONS._choices,
            required=False, # Allow for no reason
            widget=forms.CheckboxSelectMultiple(attrs={
                u'class': u'with-tooltip',
                u'data-toggle': u'tooltip',
                u'data-placement': u'right',
                u'title': lazy(render_to_string, unicode)(u'inforequests/modals/tooltips/refusal_reason-field.txt'),
                }),
            )

    def __init__(self, *args, **kwargs):
        super(RefusalReasonMixin, self).__init__(*args, **kwargs)
        if self.draft:
            self.fields[u'refusal_reason'].required = False

    def save(self, action):
        super(RefusalReasonMixin, self).save(action)
        action.refusal_reason = self.cleaned_data[u'refusal_reason']

    def save_to_draft(self, draft):
        super(RefusalReasonMixin, self).save_to_draft(draft)
        draft.refusal_reason = self.cleaned_data[u'refusal_reason']

    def load_from_draft(self, draft):
        super(RefusalReasonMixin, self).load_from_draft(draft)
        self.initial[u'refusal_reason'] = draft.refusal_reason


class DecideEmailCommonForm(FileNumberMixin, ActionAbstractForm):
    pass

class ConfirmationEmailForm(DecideEmailCommonForm):
    template = u'inforequests/modals/confirmation-email.html'
    action_type = Action.TYPES.CONFIRMATION

class ExtensionEmailForm(DeadlineMixin, DecideEmailCommonForm):
    template = u'inforequests/modals/extension-email.html'
    action_type = Action.TYPES.EXTENSION

class AdvancementEmailForm(DisclosureLevelMixin, AdvancedToMixin, DecideEmailCommonForm):
    template = u'inforequests/modals/advancement-email.html'
    action_type = Action.TYPES.ADVANCEMENT

class ClarificationRequestEmailForm(DecideEmailCommonForm):
    template = u'inforequests/modals/clarification_request-email.html'
    action_type = Action.TYPES.CLARIFICATION_REQUEST

class DisclosureEmailForm(DisclosureLevelMixin, DecideEmailCommonForm):
    template = u'inforequests/modals/disclosure-email.html'
    action_type = Action.TYPES.DISCLOSURE

class RefusalEmailForm(RefusalReasonMixin, DecideEmailCommonForm):
    template = u'inforequests/modals/refusal-email.html'
    action_type = Action.TYPES.REFUSAL


class AddSmailCommonForm(AttachmentsMixin, SubjectContentMixin, FileNumberMixin, EffectiveDateMixin, ActionAbstractForm):
    def clean(self):
        cleaned_data = super(AddSmailCommonForm, self).clean()

        if not self.draft:
            if self.inforequest.has_undecided_emails:
                msg = squeeze(render_to_string(u'inforequests/messages/add_smail-undecided_emails.txt', {
                        u'inforequest': self.inforequest,
                        }))
                raise forms.ValidationError(msg, code=u'undecided_emails')

        return cleaned_data

class ConfirmationSmailForm(AddSmailCommonForm):
    template = u'inforequests/modals/confirmation-smail.html'
    action_type = Action.TYPES.CONFIRMATION

class ExtensionSmailForm(DeadlineMixin, AddSmailCommonForm):
    template = u'inforequests/modals/extension-smail.html'
    action_type = Action.TYPES.EXTENSION

class AdvancementSmailForm(DisclosureLevelMixin, AdvancedToMixin, AddSmailCommonForm):
    template = u'inforequests/modals/advancement-smail.html'
    action_type = Action.TYPES.ADVANCEMENT

class ClarificationRequestSmailForm(AddSmailCommonForm):
    template = u'inforequests/modals/clarification_request-smail.html'
    action_type = Action.TYPES.CLARIFICATION_REQUEST

class DisclosureSmailForm(DisclosureLevelMixin, AddSmailCommonForm):
    template = u'inforequests/modals/disclosure-smail.html'
    action_type = Action.TYPES.DISCLOSURE

class RefusalSmailForm(RefusalReasonMixin, AddSmailCommonForm):
    template = u'inforequests/modals/refusal-smail.html'
    action_type = Action.TYPES.REFUSAL

class AffirmationSmailForm(RefusalReasonMixin, AddSmailCommonForm):
    template = u'inforequests/modals/affirmation-smail.html'
    action_type = Action.TYPES.AFFIRMATION

class ReversionSmailForm(DisclosureLevelMixin, AddSmailCommonForm):
    template = u'inforequests/modals/reversion-smail.html'
    action_type = Action.TYPES.REVERSION

class RemandmentSmailForm(DisclosureLevelMixin, AddSmailCommonForm):
    template = u'inforequests/modals/remandment-smail.html'
    action_type = Action.TYPES.REMANDMENT


class NewActionCommonForm(AttachmentsMixin, SubjectContentMixin, ActionAbstractForm):
    def clean(self):
        cleaned_data = super(NewActionCommonForm, self).clean()

        if not self.draft:
            if self.inforequest.has_undecided_emails:
                msg = squeeze(render_to_string(u'inforequests/messages/new_action-undecided_emails.txt', {
                        u'inforequest': self.inforequest,
                        }))
                raise forms.ValidationError(msg, code=u'undecided_emails')

        return cleaned_data

class ClarificationResponseForm(NewActionCommonForm):
    template = u'inforequests/modals/clarification_response.html'
    action_type = Action.TYPES.CLARIFICATION_RESPONSE

class AppealForm(NewActionCommonForm):
    template = u'inforequests/modals/appeal.html'
    action_type = Action.TYPES.APPEAL


class ExtendDeadlineForm(PrefixedForm):
    template = u'inforequests/modals/extend-deadline.html'

    extension = forms.IntegerField(
            label=_(u'inforequests:ExtendDeadlineForm:extension:label'),
            initial=5,
            min_value=2,
            max_value=100,
            widget=forms.NumberInput(attrs={
                u'placeholder': _(u'inforequests:ExtendDeadlineForm:extension:placeholder'),
                u'class': u'with-tooltip',
                u'data-toggle': u'tooltip',
                u'title': lazy(render_to_string, unicode)(u'inforequests/modals/tooltips/extend_deadline.txt'),
                }),
            )

    def save(self, action):
        assert self.is_valid()
        assert action.deadline is not None

        # User sets the extended deadline relative to today.
        action.extension = action.days_passed - action.deadline + self.cleaned_data[u'extension']
