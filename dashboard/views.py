from django.shortcuts import render


def index(request, **kwargs):
    if request.user.is_authenticated:
        members = request.user.member_set.all()
    else:
        members = None
    if not members:
        return render(request, 'dashboard.html')
    if 'project' not in kwargs:
        kwargs['project'] = request.user.member_set.first().project
    context = {
        'members': members,
        'project': kwargs['project']
    }
    return render(request, 'dashboard.html', context=context)
