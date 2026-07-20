import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Download, FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ExportButtons({ module, className }) {
  const [exporting, setExporting] = useState(null);

  const handleExport = async (format) => {
    setExporting(format);
    try {
      const response = await axios.get(`${API}/export/${module}/${format}`, {
        withCredentials: true,
        responseType: "blob",
      });
      
      const ext = format === "excel" ? "xlsx" : "pdf";
      const mime = format === "excel" 
        ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" 
        : "application/pdf";
      
      const blob = new Blob([response.data], { type: mime });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${module}_sirius.${ext}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      toast.success(`Exportado como ${format.toUpperCase()} com sucesso!`);
    } catch (error) {
      toast.error("Erro ao exportar. Tente novamente.");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className={"flex items-center gap-2 " + (className || "")}>
      <Button
        variant="outline"
        size="sm"
        onClick={() => handleExport("excel")}
        disabled={exporting !== null}
        className="border-[#27272A] text-[#A1A1AA] hover:text-white hover:border-[#22C55E] transition-colors text-xs gap-1.5"
      >
        {exporting === "excel" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileSpreadsheet className="w-3.5 h-3.5" />}
        Excel
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => handleExport("pdf")}
        disabled={exporting !== null}
        className="border-[#27272A] text-[#A1A1AA] hover:text-white hover:border-[#FF3B30] transition-colors text-xs gap-1.5"
      >
        {exporting === "pdf" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />}
        PDF
      </Button>
    </div>
  );
}
