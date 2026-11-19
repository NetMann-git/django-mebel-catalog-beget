from .copy_registry import PAGES
from .models import EditablePage


def page_text(key, request=None):
    cache = getattr(request,'_page_text_cache',{}) if request is not None else {}
    if key in cache:
        return cache[key]
    definition = PAGES[key]
    row = EditablePage.objects.filter(key=key).first()
    source = row.draft if row and getattr(request,'copy_preview_key',None)==key else row.published if row else {}
    source = source if isinstance(source,dict) else {}
    values = {}
    for name,field in definition['fields'].items():
        value=source.get(name,field['default'])
        expected=bool if field.get('boolean') else str
        values[name]=value if isinstance(value,expected) else field['default']
    values['faqs']=[{'question':values[name], 'answer':values[name.replace('_question','_answer')]} for name in definition['fields'] if name.startswith('faq_') and name.endswith('_question') and values.get(name.replace('_question','_enabled'),True)]
    cache[key]=values
    if request is not None:
        request._page_text_cache=cache
    return values
