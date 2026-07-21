import React, { useState, useEffect, useCallback } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { Key, ExternalLink, Check, Loader2 } from "lucide-react"
import axios from "axios"

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api`

export function GeminiKeyModal() {
  const [open, setOpen] = useState(false)
  const [apiKey, setApiKey] = useState("")
  const [saving, setSaving] = useState(false)

  const onOpenChange = useCallback(() => {
    setOpen(false)
  }, [])

  useEffect(() => {
    const handler = () => setOpen(true)
    window.addEventListener("open-gemini-key-modal", handler)
    return () => window.removeEventListener("open-gemini-key-modal", handler)
  }, [])

  const handleSave = async () => {
    if (!apiKey.trim()) {
      toast.error("Insira uma chave API válida")
      return
    }
    setSaving(true)
    try {
      await axios.patch(`${API}/auth/profile`,
        { gemini_api_key: apiKey.trim() },
        { withCredentials: true }
      )
      toast.success("Chave Gemini salva!")
      setOpen(false)
    } catch {
      toast.error("Erro ao salvar chave. Tente novamente.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md border-[#27272A] bg-[#0A0A0B]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Key className="w-5 h-5 text-[#007AFF]" />
            Chave de API Gemini
          </DialogTitle>
          <DialogDescription className="text-[#71717A]">
            Este recurso precisa de uma chave de API do Google Gemini para funcionar.
            Configure sua chave abaixo ou vá em{" "}
            <span className="text-[#007AFF] font-medium">Perfil</span>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <Input
            type="password"
            placeholder="Cole sua chave Gemini aqui..."
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="bg-[#18181B] border-[#27272A] text-sm h-10"
          />

          <a
            href="https://makersuite.google.com/app/apikey"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-[#007AFF] hover:underline"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Obter chave no Google AI Studio
          </a>

          <div className="flex gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOpen(false)}
              className="border-[#27272A] text-[#A1A1AA] hover:bg-[#18181B]"
            >
              Agora não
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving || !apiKey.trim()}
              className="bg-[#007AFF] hover:bg-[#0066D6] text-white flex-1"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              {saving ? "Salvando..." : "Salvar chave"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
