from django import template
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag
def url_replace(request, field, value):
    """Reemplaza un parámetro en la URL"""
    dict_ = request.GET.copy()
    dict_[field] = value
    return dict_.urlencode()

@register.filter
def dict_lookup(dict_list, key):
    """Filtro para buscar un valor en una lista de tuplas"""
    if hasattr(dict_list, 'choices'):
        dict_list = dict_list.choices
    
    for k, v in dict_list:
        if str(k) == str(key):
            return v
    return key