"""Admin rich-text widgets (no extra Django apps required on production)."""
from django import forms


class RichTextAdminWidget(forms.Textarea):
    """TinyMCE editor loaded from CDN — works in admin without ckeditor in INSTALLED_APPS."""

    class Media:
        js = (
            'https://cdn.jsdelivr.net/npm/tinymce@6.8.5/tinymce.min.js',
            'JS/pdf-policy-editor.js',
        )

    def __init__(self, attrs=None):
        defaults = {
            'class': 'pdf-policy-editor',
            'rows': 28,
            'cols': 80,
            'style': 'width:100%;',
        }
        if attrs:
            defaults.update(attrs)
        super().__init__(defaults)
