import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { MAQUINAS, PRIORIDADES, STATUS_LIST } from "@/lib/notas";
import type { Nota, Prioridade, Status } from "@/lib/notas";

interface Props {
  onCriar: (nota: Omit<Nota, "id" | "numero">) => void;
}

const inicial = {
  maquina: "",
  descricao: "",
  responsavel: "",
  prioridade: "" as Prioridade | "",
  status: "Aberta" as Status,
  dataAbertura: new Date().toISOString().slice(0, 10),
};

export function FormularioNota({ onCriar }: Props) {
  const [aberto, setAberto] = useState(false);
  const [form, setForm] = useState(inicial);

  function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!form.maquina || !form.descricao.trim() || !form.responsavel.trim() || !form.prioridade) {
      toast.error("Preencha todos os campos obrigatórios.");
      return;
    }
    onCriar({
      maquina: form.maquina,
      descricao: form.descricao.trim(),
      responsavel: form.responsavel.trim(),
      prioridade: form.prioridade,
      status: form.status,
      dataAbertura: form.dataAbertura,
    });
    toast.success("Nota de manutenção cadastrada com sucesso.");
    setForm(inicial);
    setAberto(false);
  }

  return (
    <Dialog open={aberto} onOpenChange={setAberto}>
      <DialogTrigger asChild>
        <Button className="w-full sm:w-auto">
          <Plus className="size-4" />
          Nova nota
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Cadastrar nova nota</DialogTitle>
          <DialogDescription>
            Informe os dados da ocorrência de manutenção industrial.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={enviar} className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="maquina">Máquina</Label>
            <Select
              value={form.maquina}
              onValueChange={(v) => setForm((f) => ({ ...f, maquina: v }))}
            >
              <SelectTrigger id="maquina">
                <SelectValue placeholder="Selecione a máquina" />
              </SelectTrigger>
              <SelectContent>
                {MAQUINAS.map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="descricao">Descrição</Label>
            <Textarea
              id="descricao"
              rows={3}
              placeholder="Descreva a ocorrência"
              value={form.descricao}
              onChange={(e) => setForm((f) => ({ ...f, descricao: e.target.value }))}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="responsavel">Responsável</Label>
            <Input
              id="responsavel"
              placeholder="Nome do responsável"
              value={form.responsavel}
              onChange={(e) => setForm((f) => ({ ...f, responsavel: e.target.value }))}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="prioridade">Prioridade</Label>
              <Select
                value={form.prioridade}
                onValueChange={(v) => setForm((f) => ({ ...f, prioridade: v as Prioridade }))}
              >
                <SelectTrigger id="prioridade">
                  <SelectValue placeholder="Selecione" />
                </SelectTrigger>
                <SelectContent>
                  {PRIORIDADES.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="status">Status</Label>
              <Select
                value={form.status}
                onValueChange={(v) => setForm((f) => ({ ...f, status: v as Status }))}
              >
                <SelectTrigger id="status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_LIST.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="data">Data de abertura</Label>
            <Input
              id="data"
              type="date"
              value={form.dataAbertura}
              onChange={(e) => setForm((f) => ({ ...f, dataAbertura: e.target.value }))}
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setAberto(false)}>
              Cancelar
            </Button>
            <Button type="submit">Cadastrar nota</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
