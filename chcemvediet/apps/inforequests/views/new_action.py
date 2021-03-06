# vim: expandtab
# -*- coding: utf-8 -*-
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseNotFound, HttpResponseBadRequest
from django.contrib.sessions.models import Session

from poleno.utils.views import require_ajax, login_required
from poleno.utils.forms import clean_button
from poleno.utils.date import local_today
from chcemvediet.apps.wizards import WizzardRollback
from chcemvediet.apps.inforequests import forms
from chcemvediet.apps.inforequests.models import Inforequest, Branch, Action, ActionDraft
from chcemvediet.apps.inforequests.forms import AppealWizards

from .shortcuts import render_form, render_step, json_form, json_step, json_draft, json_success

@require_http_methods([u'HEAD', u'GET', u'POST'])
@require_ajax
@transaction.atomic
@login_required(raise_exception=True)
def _new_action(request, inforequest_pk, form_class):
    assert form_class.action_type in Action.APPLICANT_ACTION_TYPES

    inforequest = (Inforequest.objects
            .not_closed()
            .owned_by(request.user)
            .prefetch_related(Inforequest.prefetch_branches(None, Branch.objects.select_related(u'historicalobligee')))
            .prefetch_related(Branch.prefetch_last_action(u'branches'))
            .get_or_404(pk=inforequest_pk)
            )

    if request.method != u'POST': # The user can save a draft even if he may not submit.
        if inforequest.has_undecided_emails:
            return HttpResponseNotFound()
        if not inforequest.can_add_action(form_class.action_type):
            return HttpResponseNotFound()

    draft = inforequest.actiondraft_set.filter(type=form_class.action_type).order_by_pk().first()
    session = Session.objects.get(session_key=request.session.session_key)
    attached_to = (session, draft) if draft else (session,)

    if request.method != u'POST':
        form = form_class(inforequest=inforequest, attached_to=attached_to)
        if draft:
            form.load_from_draft(draft)
        return render_form(request, form, inforequest=inforequest)

    if form_class.action_type in Action.APPLICANT_EMAIL_ACTION_TYPES:
        button = clean_button(request.POST, [u'email', u'print', u'draft'])
    else:
        button = clean_button(request.POST, [u'print', u'draft'])

    if button == u'draft':
        form = form_class(request.POST, inforequest=inforequest, attached_to=attached_to, draft=True)
        if not form.is_valid():
            return json_form(request, form, inforequest=inforequest)
        if not draft:
            draft = ActionDraft(inforequest=inforequest, type=form_class.action_type)
        form.save_to_draft(draft)
        draft.save()
        return json_draft()

    if button in [u'email', u'print']:
        form = form_class(request.POST, inforequest=inforequest, attached_to=attached_to)
        if not form.is_valid():
            return json_form(request, form, inforequest=inforequest)
        if form_class.action_type == Action.TYPES.APPEAL:
            form.cleaned_data[u'branch'].add_expiration_if_expired()
        action = Action(effective_date=local_today(), type=form_class.action_type)
        form.save(action)
        action.save()
        if draft:
            draft.delete()
        # The inforequest was changed, we need to refetch it.
        inforequest = Inforequest.objects.prefetch_detail().get(pk=inforequest.pk)
        action.branch = inforequest.branch_by_pk(action.branch_id)
        if button == u'email':
            action.send_by_email()
        return json_success(request, inforequest, action, button == u'print')

    return HttpResponseBadRequest()

def new_action_clarification_response(request, inforequest_pk):
    return _new_action(request, inforequest_pk, forms.ClarificationResponseForm)

def new_action_appeal(request, inforequest_pk):
    return _new_action(request, inforequest_pk, forms.AppealForm)


@require_http_methods([u'HEAD', u'GET', u'POST'])
@require_ajax
@transaction.atomic
@login_required(raise_exception=True)
def new_action_appeal2(request, inforequest_pk, branch_pk):
    inforequest = Inforequest.objects.not_closed().owned_by(request.user).get_or_404(pk=inforequest_pk)
    branch = inforequest.branch_set.get_or_404(pk=branch_pk)

    if not branch.can_add_appeal:
        return HttpResponseNotFound()
    if inforequest.has_undecided_emails:
        return HttpResponseNotFound()

    wizard = AppealWizards.find_applicable(branch)

    if request.method != u'POST':
        wizard.start()
        return render_step(request, wizard.current_step)

    try:
        wizard.step(request.POST)
    except WizzardRollback as e:
        return json_step(request, e.step)

    button = clean_button(request.POST, [u'save', u'prev', u'next'])

    if button == u'save':
        wizard.commit()
        return json_step(request, wizard.current_step)

    if button == u'prev':
        return json_step(request, wizard.prev_step())

    if button == u'next':
        if not wizard.current_step.is_valid():
            return json_step(request, wizard.current_step)
        wizard.commit()
        if not wizard.current_step.is_last():
            return json_step(request, wizard.next_step())
        branch.add_expiration_if_expired()
        action = Action(type=Action.TYPES.APPEAL)
        wizard.save(action)
        action.save()
        # The inforequest was changed, we need to refetch it.
        inforequest = Inforequest.objects.prefetch_detail().get(pk=inforequest.pk)
        return json_success(request, inforequest, action)

    return HttpResponseBadRequest()
