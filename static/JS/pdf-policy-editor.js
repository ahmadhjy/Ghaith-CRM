(function () {
    'use strict';

    function initPdfPolicyEditors() {
        if (typeof tinymce === 'undefined') {
            return;
        }
        document.querySelectorAll('textarea.pdf-policy-editor').forEach(function (el) {
            if (el.dataset.tinymceInit === '1') {
                return;
            }
            el.dataset.tinymceInit = '1';
            tinymce.init({
                target: el,
                height: 420,
                menubar: 'edit view insert format',
                plugins: 'lists link code table autoresize',
                toolbar: [
                    'undo redo | blocks | bold italic underline strikethrough',
                    '| alignleft aligncenter alignright alignjustify',
                    '| bullist numlist outdent indent',
                    '| link | removeformat code',
                ].join(' '),
                branding: false,
                promotion: false,
                license_key: 'gpl',
                content_style: 'body { font-family: Helvetica, Arial, sans-serif; font-size: 14px; }',
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPdfPolicyEditors);
    } else {
        initPdfPolicyEditors();
    }

    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).ready(initPdfPolicyEditors);
    }
})();
