# nucleo/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden
from .models import Pqrs
from django.db.models import Count, Q
from .forms import PqrsForm, PqrsFilterForm
from datetime import date

def es_coordinador(user):
    return user.groups.filter(name='Coordinadores').exists()

@login_required
def dashboard(request):
    queryset = Pqrs.objects.all().order_by('-fecha_recepcion_inicial')
    filter_form = PqrsFilterForm(request.GET)
    
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get('q')
        vigencia = filter_form.cleaned_data.get('vigencia')
        responsable = filter_form.cleaned_data.get('responsable')
        estado = filter_form.cleaned_data.get('estado')
        
        if q:
            queryset = queryset.filter(Q(radicado__icontains=q) | Q(asunto__icontains=q))
        
        if vigencia:
            queryset = queryset.filter(fecha_recepcion_inicial__year=vigencia)
        else:
            current_year = date.today().year
            queryset = queryset.filter(fecha_recepcion_inicial__year=current_year)

        if responsable:
            queryset = queryset.filter(responsable=responsable)
        
        if estado:
            queryset = queryset.filter(estado=estado)

    total_pqrs = Pqrs.objects.count()
    conteo_por_estado = Pqrs.objects.values('estado').annotate(total=Count('estado')).order_by('estado')

    # --- LÍNEA NUEVA ---
    # Verificamos si el usuario es coordinador y guardamos el resultado
    es_coord = request.user.groups.filter(name='Coordinadores').exists()

    contexto = {
        'total_pqrs': total_pqrs,
        'conteo_por_estado': conteo_por_estado,
        'lista_pqrs': queryset,
        'filter_form': filter_form,
        'es_coordinador': es_coord # <-- ¡Añadimos la variable al contexto!
    }
    
    return render(request, 'nucleo/dashboard.html', contexto)

@login_required
@user_passes_test(es_coordinador)
def crear_pqrs(request):
    if request.method == 'POST':
        form = PqrsForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = PqrsForm()
    return render(request, 'nucleo/pqrs_form.html', {'form': form})

@login_required
def editar_pqrs(request, pqrs_id):
    pqrs = get_object_or_404(Pqrs, pk=pqrs_id)
    es_coord = request.user.groups.filter(name='Coordinadores').exists()
    if not (pqrs.responsable == request.user or es_coord or request.user.is_superuser):
        return HttpResponseForbidden("No tienes permiso para editar este caso.")
    if request.method == 'POST':
        form = PqrsForm(request.POST, instance=pqrs)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = PqrsForm(instance=pqrs)
    contexto = {
        'form': form,
        'pqrs': pqrs
    }
    return render(request, 'nucleo/pqrs_form.html', contexto)