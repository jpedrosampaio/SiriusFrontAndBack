import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function CodeBlock({ children, className }) {
  const language = className ? className.replace('language-', '') : '';
  return (
    <div className="relative my-2 rounded-md overflow-hidden">
      {language && (
        <div className="bg-[#2C2C2E] px-3 py-1 text-[10px] text-[#A1A1AA] uppercase tracking-wider border-b border-[#3A3A3C]">
          {language}
        </div>
      )}
      <pre className="bg-[#1A1A1A] p-3 overflow-x-auto text-xs leading-relaxed">
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}

export default function MarkdownRenderer({ content, className = '' }) {
  if (!content) return null;

  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Code blocks
          code({ node, inline, className: codeClassName, children, ...props }) {
            if (inline) {
              return (
                <code className="bg-[#2C2C2E] px-1.5 py-0.5 rounded text-[#00F0FF] text-xs font-mono" {...props}>
                  {children}
                </code>
              );
            }
            return <CodeBlock className={codeClassName}>{children}</CodeBlock>;
          },
          // Paragraphs
          p({ children }) {
            return <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>;
          },
          // Headers
          h1({ children }) {
            return <h1 className="text-lg font-bold mb-2 mt-3 text-white">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="text-base font-bold mb-2 mt-3 text-white">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="text-sm font-bold mb-1.5 mt-2 text-white">{children}</h3>;
          },
          // Lists
          ul({ children }) {
            return <ul className="list-disc list-inside mb-2 space-y-0.5">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="list-decimal list-inside mb-2 space-y-0.5">{children}</ol>;
          },
          li({ children }) {
            return <li className="text-xs md:text-sm">{children}</li>;
          },
          // Tables
          table({ children }) {
            return (
              <div className="overflow-x-auto my-2">
                <table className="w-full border-collapse text-xs">{children}</table>
              </div>
            );
          },
          thead({ children }) {
            return <thead className="bg-[#2C2C2E]">{children}</thead>;
          },
          th({ children }) {
            return <th className="border border-[#3A3A3C] px-2 py-1.5 text-left font-semibold text-[#A1A1AA]">{children}</th>;
          },
          td({ children }) {
            return <td className="border border-[#27272A] px-2 py-1.5">{children}</td>;
          },
          // Links
          a({ href, children }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" className="text-[#007AFF] hover:underline">
                {children}
              </a>
            );
          },
          // Blockquote
          blockquote({ children }) {
            return (
              <blockquote className="border-l-2 border-[#007AFF] pl-3 my-2 text-[#A1A1AA] italic">
                {children}
              </blockquote>
            );
          },
          // Horizontal rule
          hr() {
            return <hr className="border-[#27272A] my-3" />;
          },
          // Strong/Bold
          strong({ children }) {
            return <strong className="font-bold text-white">{children}</strong>;
          },
          // Images
          img({ src, alt }) {
            return (
              <img src={src} alt={alt} className="max-w-full rounded-md my-2 border border-[#27272A]" />
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
