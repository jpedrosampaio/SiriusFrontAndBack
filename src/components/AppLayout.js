import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";

export default function AppLayout({ user, children }) {
  return (
    <div className="flex min-h-screen bg-[#050505]">
      <Sidebar user={user} />
      <main className="flex-1 ml-0 md:ml-64 pb-20 md:pb-0">
        {children}
      </main>
      <MobileNav user={user} />
    </div>
  );
}
