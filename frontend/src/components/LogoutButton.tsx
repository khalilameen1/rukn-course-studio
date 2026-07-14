"use client";

import { useRouter } from "next/navigation";
import { clearToken } from "@/lib/auth";

export default function LogoutButton() {
  const router = useRouter();

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  return (
    <button type="button" onClick={handleLogout} className="btn-ghost">
      Logout
    </button>
  );
}
