/**
 * RichHtmlEditor — A 3-tab content editor:
 *   Rich Text  |  HTML Source  |  Preview (editable)
 *
 * All three tabs share the same `value` (HTML string).
 * Switching tabs syncs content bidirectionally so no edits are lost.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import ImageExt from "@tiptap/extension-image";
import LinkExt from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import {
  Bold, Italic, Strikethrough, List, ListOrdered, Link2,
  Image as ImageIcon, Heading1, Heading2, Heading3, Undo, Redo,
} from "lucide-react";

interface Props {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  minHeight?: string;
  withImages?: boolean;
  className?: string;
}

function ToolBtn({
  active, onClick, title, children,
}: {
  active: boolean; onClick: () => void; title: string; children: React.ReactNode;
}) {
  return (
    <button type="button" title={title} onClick={onClick}
      className={`p-1.5 rounded transition-colors text-xs ${active ? "bg-slate-800 text-white" : "text-slate-500 hover:bg-slate-100"}`}>
      {children}
    </button>
  );
}

export function RichHtmlEditor({
  value,
  onChange,
  placeholder = "Write here…",
  minHeight = "220px",
  withImages = false,
  className = "",
}: Props) {
  const [tab, setTab] = useState<"rich" | "html" | "preview">("rich");
  // Local HTML — single source of truth for HTML/Preview tabs
  const [localHtml, setLocalHtml] = useState(value);
  // Key used to force-reinit the Tiptap editor when we switch back to Rich
  // with content that was edited in HTML or Preview mode
  const [richKey, setRichKey] = useState(0);
  const previewRef = useRef<HTMLDivElement>(null);
  const isFirstRender = useRef(true);

  // Sync external value changes (e.g. template applied) into local state
  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return; }
    setLocalHtml(value);
    setRichKey(k => k + 1);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const extensions = [
    StarterKit,
    ...(withImages ? [ImageExt] : []),
    LinkExt.configure({ openOnClick: false }),
    Placeholder.configure({ placeholder }),
  ];

  const editor = useEditor({
    extensions,
    content: localHtml,
    onUpdate({ editor }) {
      const html = editor.getHTML();
      setLocalHtml(html);
      onChange(html);
    },
  });

  // Sync preview div when switching to preview tab
  useEffect(() => {
    if (tab === "preview" && previewRef.current) {
      const el = previewRef.current;
      if (el.innerHTML !== localHtml) {
        el.innerHTML = localHtml;
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const handleTabChange = useCallback((newTab: "rich" | "html" | "preview") => {
    if (newTab === tab) return;

    // Capture current content before switching
    let currentHtml = localHtml;
    if (tab === "preview" && previewRef.current) {
      currentHtml = previewRef.current.innerHTML;
      setLocalHtml(currentHtml);
      onChange(currentHtml);
    }

    // When switching back to Rich, reinit editor with latest HTML
    if (newTab === "rich" && currentHtml !== localHtml) {
      if (editor && !editor.isDestroyed) {
        editor.commands.setContent(currentHtml);
      } else {
        setRichKey(k => k + 1);
      }
    } else if (newTab === "rich" && editor && !editor.isDestroyed) {
      editor.commands.setContent(currentHtml);
      setRichKey(k => k + 1);
    }

    setTab(newTab);
  }, [tab, localHtml, editor, onChange]);

  const handlePreviewInput = useCallback(() => {
    if (previewRef.current) {
      const html = previewRef.current.innerHTML;
      setLocalHtml(html);
      onChange(html);
    }
  }, [onChange]);

  const handleHtmlChange = (raw: string) => {
    setLocalHtml(raw);
    onChange(raw);
  };

  const insertImage = () => {
    const url = prompt("Enter image URL:");
    if (url && editor) editor.chain().focus().setImage({ src: url }).run();
  };

  const setLink = () => {
    const url = prompt("Enter URL:");
    if (url && editor) editor.chain().focus().setLink({ href: url }).run();
    else if (editor) editor.chain().focus().unsetLink().run();
  };

  return (
    <div className={`border border-slate-200 rounded-lg overflow-hidden ${className}`} data-testid="rich-html-editor">
      {/* Tab bar */}
      <div className="flex border-b border-slate-200 bg-slate-50">
        {(["rich", "html", "preview"] as const).map(t => (
          <button key={t} type="button" onClick={() => handleTabChange(t)}
            className={`px-4 py-1.5 text-xs font-medium transition-colors border-b-2 ${tab === t ? "border-slate-900 text-slate-900 bg-white" : "border-transparent text-slate-500 hover:text-slate-700"}`}
            data-testid={`rhe-tab-${t}`}>
            {t === "rich" ? "Rich Text" : t === "html" ? "HTML" : "Preview"}
          </button>
        ))}
      </div>

      {/* Rich Text tab */}
      {tab === "rich" && editor && (
        <>
          <div className="flex flex-wrap gap-0.5 p-2 border-b border-slate-200 bg-slate-50">
            <ToolBtn active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()} title="Bold"><Bold size={13} /></ToolBtn>
            <ToolBtn active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()} title="Italic"><Italic size={13} /></ToolBtn>
            <ToolBtn active={editor.isActive("strike")} onClick={() => editor.chain().focus().toggleStrike().run()} title="Strikethrough"><Strikethrough size={13} /></ToolBtn>
            <div className="w-px bg-slate-200 mx-1 self-stretch" />
            <ToolBtn active={editor.isActive("heading", { level: 1 })} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} title="Heading 1"><Heading1 size={13} /></ToolBtn>
            <ToolBtn active={editor.isActive("heading", { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} title="Heading 2"><Heading2 size={13} /></ToolBtn>
            <ToolBtn active={editor.isActive("heading", { level: 3 })} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} title="Heading 3"><Heading3 size={13} /></ToolBtn>
            <div className="w-px bg-slate-200 mx-1 self-stretch" />
            <ToolBtn active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()} title="Bullet list"><List size={13} /></ToolBtn>
            <ToolBtn active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()} title="Numbered list"><ListOrdered size={13} /></ToolBtn>
            <div className="w-px bg-slate-200 mx-1 self-stretch" />
            <ToolBtn active={editor.isActive("link")} onClick={setLink} title="Insert / edit link"><Link2 size={13} /></ToolBtn>
            {withImages && (
              <ToolBtn active={false} onClick={insertImage} title="Insert image"><ImageIcon size={13} /></ToolBtn>
            )}
            <div className="w-px bg-slate-200 mx-1 self-stretch" />
            <ToolBtn active={false} onClick={() => editor.chain().focus().undo().run()} title="Undo"><Undo size={13} /></ToolBtn>
            <ToolBtn active={false} onClick={() => editor.chain().focus().redo().run()} title="Redo"><Redo size={13} /></ToolBtn>
          </div>
          <EditorContent key={richKey} editor={editor}
            className="prose prose-sm max-w-none p-4 outline-none [&_.tiptap]:outline-none"
            style={{ minHeight }} />
        </>
      )}

      {/* HTML tab */}
      {tab === "html" && (
        <textarea
          value={localHtml}
          onChange={e => handleHtmlChange(e.target.value)}
          className="w-full p-3 font-mono text-xs text-slate-700 outline-none resize-none bg-white focus:outline-none"
          style={{ minHeight }}
          spellCheck={false}
          data-testid="rhe-html-textarea"
          placeholder="<p>Write HTML here…</p>"
        />
      )}

      {/* Preview tab — contentEditable for in-place editing */}
      {tab === "preview" && (
        <div
          ref={previewRef}
          contentEditable
          suppressContentEditableWarning
          onInput={handlePreviewInput}
          className="prose prose-sm max-w-none p-4 outline-none focus:outline-none [&:empty]:before:content-[attr(data-placeholder)] [&:empty]:before:text-slate-400"
          data-placeholder={placeholder}
          style={{ minHeight }}
          data-testid="rhe-preview"
        />
      )}
    </div>
  );
}
