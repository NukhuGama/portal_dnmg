/* Shared admin rich-text editors and repeatable formsets, including HTMX navigation. */
(function () {
    'use strict';

    function initializeEditor(editor) {
        var targetSelector = editor.dataset.richEditorTarget;
        var contentField = targetSelector ? document.querySelector(targetSelector) : null;
        if (!editor || !contentField || editor.dataset.initialized === 'true') {
            return;
        }

        editor.dataset.initialized = 'true';
        editor.innerHTML = contentField.value || '';
        var editorContainer = editor.closest('[data-rich-editor-container]') || editor.parentElement;

        function syncContent() {
            contentField.value = editor.innerHTML;
        }

        function insertTextAtCursor(value) {
            editor.focus();
            var selection = window.getSelection();
            var range;

            if (selection.rangeCount && editor.contains(selection.anchorNode)) {
                range = selection.getRangeAt(0);
            } else {
                range = document.createRange();
                range.selectNodeContents(editor);
                range.collapse(false);
            }

            range.deleteContents();
            var text = document.createTextNode(value);
            range.insertNode(text);
            range.setStartAfter(text);
            selection.removeAllRanges();
            selection.addRange(range);
        }

        editorContainer.querySelectorAll('[data-editor-command]').forEach(function (button) {
            button.addEventListener('mousedown', function (event) { event.preventDefault(); });
            button.addEventListener('click', function () {
                editor.focus();
                document.execCommand(button.dataset.editorCommand, false, button.dataset.editorValue || null);
                syncContent();
            });
        });

        var linkButton = editorContainer.querySelector('[data-editor-link]');
        if (linkButton) {
            linkButton.addEventListener('mousedown', function (event) { event.preventDefault(); });
            linkButton.addEventListener('click', function () {
                var url = window.prompt(editor.dataset.linkPrompt || 'Enter a link');
                if (url) {
                    editor.focus();
                    document.execCommand('createLink', false, url);
                    syncContent();
                }
            });
        }

        editorContainer.querySelectorAll('[data-editor-icon]').forEach(function (button) {
            button.addEventListener('mousedown', function (event) { event.preventDefault(); });
            button.addEventListener('click', function () {
                var emoji = button.dataset.editorEmoji;
                if (emoji) {
                    insertTextAtCursor(emoji + '\u00a0');
                } else {
                    editor.focus();
                    document.execCommand(
                        'insertHTML',
                        false,
                        '<i class="bi bi-' + button.dataset.editorIcon + '"></i> '
                    );
                }
                syncContent();
            });
        });

        editor.addEventListener('input', syncContent);
        editor.closest('form').addEventListener('submit', syncContent);
    }

    function initializeEditors(scope) {
        var editors = [];
        if (scope.matches && scope.matches('[data-rich-editor]')) {
            editors.push(scope);
        }
        if (scope.querySelectorAll) {
            editors = editors.concat(Array.from(scope.querySelectorAll('[data-rich-editor]')));
        }
        editors.forEach(initializeEditor);
    }

    function initializeFormsets(scope) {
        scope.querySelectorAll('[data-add-form]').forEach(function (button) {
            if (button.dataset.initialized === 'true') {
                return;
            }
            button.dataset.initialized = 'true';
            button.addEventListener('click', function () {
                var prefix = button.dataset.addForm;
                var totalForms = document.getElementById('id_' + prefix + '-TOTAL_FORMS');
                var template = document.getElementById(prefix + '_empty_form');
                var destination = document.getElementById(prefix + '_form_list');
                if (!totalForms || !template || !destination) {
                    return;
                }
                destination.insertAdjacentHTML(
                    'beforeend',
                    template.innerHTML.replaceAll('__prefix__', totalForms.value)
                );
                totalForms.value = Number(totalForms.value) + 1;
            });
        });
    }

    function initialize(scope) {
        initializeEditors(scope);
        initializeFormsets(scope);
    }

    document.addEventListener('DOMContentLoaded', function () { initialize(document); });
    document.body.addEventListener('htmx:afterSwap', function (event) { initialize(event.target); });
}());
