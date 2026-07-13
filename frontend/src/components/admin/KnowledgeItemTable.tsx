"use client";

import type { AdminKnowledgeItem } from "@/lib/types";

export default function KnowledgeItemTable({
  items,
  onEdit,
  onDelete,
  onActivate,
}: {
  items: AdminKnowledgeItem[];
  onEdit: (item: AdminKnowledgeItem) => void;
  onDelete: (item: AdminKnowledgeItem) => void;
  onActivate: (item: AdminKnowledgeItem) => void;
}) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        No knowledge items yet. Add the first one below.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-black/10 text-zinc-500 dark:border-white/10">
            <th className="py-2 pr-4">Key</th>
            <th className="py-2 pr-4">Title</th>
            <th className="py-2 pr-4">Type</th>
            <th className="py-2 pr-4">Version</th>
            <th className="py-2 pr-4">Active</th>
            <th className="py-2 pr-4" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b border-black/5 dark:border-white/5">
              <td className="py-2 pr-4 font-mono text-xs">{item.key}</td>
              <td className="py-2 pr-4">{item.title}</td>
              <td className="py-2 pr-4">{item.item_type}</td>
              <td className="py-2 pr-4">{item.version}</td>
              <td className="py-2 pr-4">
                {item.is_active ? (
                  <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800 dark:bg-green-900 dark:text-green-200">
                    active
                  </span>
                ) : (
                  <span className="text-zinc-400">inactive</span>
                )}
              </td>
              <td className="flex gap-2 py-2 pr-4 whitespace-nowrap">
                <button onClick={() => onEdit(item)} className="hover:underline">
                  Edit
                </button>
                {!item.is_active ? (
                  <button onClick={() => onActivate(item)} className="hover:underline">
                    Activate
                  </button>
                ) : null}
                <button
                  onClick={() => onDelete(item)}
                  className="text-red-600 hover:underline"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
