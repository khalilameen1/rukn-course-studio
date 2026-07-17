"use client";

import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";

export default function LogoutButton() {
  const router = useRouter();

  async function handleLogout() {
    try {
      if (getToken()) {
        await api.logout();
      }
    } catch {
      /* still clear local session */
    }
    clearToken();
    router.replace("/login");
  }

  return (
    <button type="button" onClick={handleLogout} className="btn-ghost">
      Logout
    </button>
  );
}
