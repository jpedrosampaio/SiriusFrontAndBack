import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FileText, Download, Sparkles, ChevronDown } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function ReportAccordionItem({ report }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Card className="bg-[#0A0A0A] border-[#27272A] overflow-hidden">
      {/* Header - Always visible, clickable to toggle */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-5 hover:bg-[#111111] transition-colors cursor-pointer text-left"
        data-testid={`report-toggle-${report.report_id}`}
      >
        <div className="flex items-center space-x-4">
          <div className="w-10 h-10 bg-[#00F0FF]/20 rounded-sm flex items-center justify-center shrink-0">
            <FileText className="w-5 h-5 text-[#00F0FF]" />
          </div>
          <div>
            <h3 className="font-heading text-lg mb-0.5">
              RELATÓRIO {(report.type || '').toUpperCase()}
            </h3>
            <p className="text-xs text-[#A1A1AA]">
              Período: {report.period || ''} | Gerado em: {report.created_at ? new Date(report.created_at).toLocaleString('pt-BR') : ''}
            </p>
          </div>
        </div>
        <ChevronDown
          className={`w-5 h-5 text-[#A1A1AA] shrink-0 ml-4 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Collapsible content */}
      <div
        className={`transition-all duration-300 ease-in-out overflow-hidden ${isOpen ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'}`}
      >
        <div className="px-5 pb-5 border-t border-[#27272A]">
          {/* Download button */}
          <div className="flex justify-end pt-3 mb-3">
            <Button
              variant="outline"
              size="sm"
              className="border-[#27272A] hover:bg-[#121212] text-xs"
              onClick={async () => {
                try {
                  const res = await axios.get(`${API}/reports/${report.report_id}/download`, {
                    withCredentials: true,
                    responseType: 'blob'
                  });
                  const url = window.URL.createObjectURL(new Blob([res.data]));
                  const link = document.createElement('a');
                  link.href = url;
                  link.setAttribute('download', `sirius_relatorio_${report.report_id}.txt`);
                  document.body.appendChild(link);
                  link.click();
                  link.remove();
                  window.URL.revokeObjectURL(url);
                  toast.success("Relatório exportado!");
                } catch (err) {
                  toast.error("Erro ao exportar relatório");
                }
              }}
            >
              <Download className="w-3.5 h-3.5 mr-2" />
              Exportar
            </Button>
          </div>

          {/* Period data */}
          <div className="bg-[#121212] border border-[#27272A] rounded-sm p-4 mb-4">
            <h4 className="font-heading text-sm text-[#A1A1AA] uppercase tracking-wider mb-3">Dados do Período</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-[#A1A1AA] mb-1">Tarefas</p>
                <p className="font-data text-lg">{report.data?.tasks_completed ?? 0}/{report.data?.tasks ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-[#A1A1AA] mb-1">Hábitos</p>
                <p className="font-data text-lg">{report.data?.total_habits_completions ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-[#A1A1AA] mb-1">Receitas</p>
                <p className="font-data text-lg text-[#39FF14]">R$ {(report.data?.income ?? 0).toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs text-[#A1A1AA] mb-1">Despesas</p>
                <p className="font-data text-lg text-[#FF3B30]">R$ {(report.data?.expenses ?? 0).toFixed(2)}</p>
              </div>
            </div>
          </div>

          {/* Insights */}
          <div>
            <h4 className="font-heading text-sm text-[#A1A1AA] uppercase tracking-wider mb-3 flex items-center">
              <Sparkles className="w-4 h-4 mr-2 text-[#00F0FF]" />
              Insights & Sugestões
            </h4>
            <div className="prose prose-invert max-w-none">
              <p className="text-sm text-white whitespace-pre-wrap">{report.insights}</p>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function Reports() {
  const [user, setUser] = useState(null);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [reportType, setReportType] = useState("diário");

  useEffect(() => {
    fetchUser();
    fetchReports();
  }, []);

  const fetchUser = async () => {
    try {
      const res = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(res.data);
    } catch (error) {
      toast.error("Erro ao carregar usuário");
    }
  };

  const fetchReports = async () => {
    try {
      const res = await axios.get(`${API}/reports`, { withCredentials: true });
      setReports(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      toast.error("Erro ao carregar relatórios");
    }
  };

  const handleGenerateReport = async () => {
    setLoading(true);
    const periodMap = { "diário": "hoje", "semanal": "esta semana", "mensal": "este mês", "sprint": "esta semana" };
    const period = periodMap[reportType] || "hoje";
    try {
      await axios.post(`${API}/reports/generate?report_type=${reportType}&period=${period}`, {}, {
        withCredentials: true
      });
      toast.success("Relatório gerado com sucesso!");
      fetchReports();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao gerar relatório");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-[#050505]">
      <Sidebar user={user} />
      <div className="flex-1 ml-0 md:ml-64 page-container pb-24 md:pb-8 pt-[72px] md:pt-0 page-enter">
        <div className="max-w-6xl mx-auto">
          <div className="mb-8">
            <h1 className="font-heading text-3xl md:text-4xl mb-2" data-testid="reports-title">RELATÓRIOS INTELIGENTES</h1>
            <p className="text-[#A1A1AA]">Análises e insights com IA</p>
          </div>

          <Card className="bg-[#0A0A0A] border-[#27272A] p-6 mb-8">
            <div className="flex items-center space-x-4">
              <Sparkles className="w-8 h-8 text-[#00F0FF]" />
              <div className="flex-1">
                <h3 className="font-heading text-xl mb-2">GERAR NOVO RELATÓRIO</h3>
                <div className="flex items-center space-x-4">
                  <div className="flex-1">
                    <Select value={reportType} onValueChange={setReportType}>
                      <SelectTrigger data-testid="report-type-select" className="bg-[#121212] border-[#27272A] text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                        <SelectItem value="diário">Diário (Hoje)</SelectItem>
                        <SelectItem value="semanal">Semanal (Esta Semana)</SelectItem>
                        <SelectItem value="mensal">Mensal (Este Mês)</SelectItem>
                        <SelectItem value="sprint">Fim de Sprint</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button
                    data-testid="generate-report-btn"
                    onClick={handleGenerateReport}
                    disabled={loading}
                    className="bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs tracking-widest"
                  >
                    {loading ? "Gerando..." : "Gerar Relatório"}
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          <div className="space-y-4">
            {reports.length === 0 ? (
              <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                <FileText className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                <p className="text-[#A1A1AA]">Nenhum relatório gerado ainda</p>
              </Card>
            ) : (
              reports.map((report) => (
                <ReportAccordionItem key={report.report_id} report={report} />
              ))
            )}
          </div>
        </div>
      </div>
      <MobileNav user={user} />
    </div>
  );
}

