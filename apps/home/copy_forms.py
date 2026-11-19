from django import forms
from .copy_registry import PAGES


class CopyForm(forms.Form):
    revision=forms.IntegerField(min_value=0,widget=forms.HiddenInput)

    def __init__(self,key,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for name,definition in PAGES[key]['fields'].items():
            if definition.get('boolean'):
                self.fields[name]=forms.BooleanField(label=definition['label'],required=False)
            else:
                widget=forms.Textarea(attrs={'rows':3}) if definition.get('multiline') else forms.TextInput()
                self.fields[name]=forms.CharField(label=definition['label'],max_length=definition['max_length'],widget=widget)
        self.groups=[]
        for name,definition in PAGES[key]['fields'].items():
            group=next((item for item in self.groups if item['title']==definition['group']),None)
            if group is None:
                group={'title':definition['group'],'fields':[]};self.groups.append(group)
            group['fields'].append(self[name])

        self.groups.sort(key=lambda group: group['title']=='Поисковые системы')
