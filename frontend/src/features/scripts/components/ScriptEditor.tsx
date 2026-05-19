"use client";

import Link from "@tiptap/extension-link";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect } from "react";

import { cn } from "@/lib/utils";

interface Props {
  value: string;
  onChange: (next: string) => void;
  editable: boolean;
  placeholder?: string;
}

export function ScriptEditor({ value, onChange, editable, placeholder }: Props) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
      Link.configure({ openOnClick: false, autolink: true }),
    ],
    // We store the body_markdown field as Tiptap HTML for Phase 1 — backend is
    // schema-agnostic about the contents. A real markdown round-trip ships in
    // a follow-up (would add a tiptap-markdown extension).
    content: value,
    editable,
    immediatelyRender: false,
    onUpdate: ({ editor: ed }) => {
      onChange(ed.getHTML());
    },
    editorProps: {
      attributes: {
        class: cn(
          "prose prose-sm dark:prose-invert max-w-none min-h-[300px] focus:outline-none px-4 py-3",
        ),
        "data-placeholder": placeholder ?? "",
      },
    },
  });

  // Sync external content changes (e.g. switching versions).
  useEffect(() => {
    if (!editor) return;
    if (editor.getHTML() !== value) {
      editor.commands.setContent(value || "", { emitUpdate: false });
    }
  }, [value, editor]);

  // Toggle editability.
  useEffect(() => {
    editor?.setEditable(editable);
  }, [editor, editable]);

  return (
    <div className="rounded-md border">
      <EditorContent editor={editor} />
    </div>
  );
}
