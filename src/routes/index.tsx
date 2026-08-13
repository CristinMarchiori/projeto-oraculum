import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Factory, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Indicadores } from "@/components/painel/Indicadores";
import { Graficos } from "@/components/painel/Graficos";
import { TabelaNotas } from "@/components/painel/TabelaNotas";
import { FormularioNota } from "@/components/painel/FormularioNota";
import { MAQUINAS, NOTAS_INICIAIS, PRIORIDADES, STATUS_LIST } from "@/lib/notas";
import type { Nota } from "@/lib/notas";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Painel de Manutenção — Notas Industriais" },
      {
        name: "description",
        content:
          "Painel para acompanhamento de notas de manutenção industrial: indicadores, filtros, gráficos e cadastro de novas notas.",
      },
      { property: "og:title", content: "Painel de Manutenção — Notas Industriais" },
      {
        property: "og:description",
        content:
          "Acompanhe notas abertas, em andamento, concluídas e críticas por máquina, prioridade e status.",
      },
    ],
  }),
  component: Painel,
});

const TODOS = "todos";

function Painel() {
  const [notas, setNotas] = useState<Nota[]>(NOTAS_INICIAIS);
  const [busca, setBusca] = useState("");
  const [maquina, setMaquina] = useState(TODOS);
  const [prioridade, setPrioridade] = useState(TODOS);
  const [status, setStatus] = useState(TODOS);

  const filtradas = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return notas.filter(
      (n) =>
        (maquina === TODOS || n.maquina === maquina) &&
        (prioridade === TODOS || n.prioridade === prioridade) &&
        (status === TODOS || n.status === status) &&
        (termo === "" ||
          n.numero.toLowerCase().includes(termo) ||
          n.descricao.toLowerCase().includes(termo)),
    );
  }, [notas, busca, maquina, prioridade, status]);

  function criarNota(dados: Omit<Nota, "id" | "numero">) {
    setNotas((atual) => {
      const proximo = 1001 + atual.length;
      return [
        { ...dados, id: crypto.randomUUID(), numero: `NM-${proximo}` },
        ...atual,
      ];
    });
  }

  function limpar() {
    setBusca("");
    setMaquina(TODOS);
    setPrioridade(TODOS);
    setStatus(TODOS);
  }

  return (
    <div className="min-h-screen bg-background">
      <header
        className="border-b border-border text-primary-foreground"
        style={{ backgroundImage: "var(--gradient-header)" }}
      >
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <span className="flex size-11 items-center justify-center rounded-md bg-primary-foreground/10">
              <Factory className="size-6" />
            </span>
            <div>
              <h1 className="font-display text-2xl font-bold uppercase tracking-wide sm:text-3xl">
                Painel de Manutenção
              </h1>
              <p className="text-sm text-primary-foreground/70">
                Acompanhamento de notas de manutenção industrial
              </p>
            </div>
          </div>
          <FormularioNota onCriar={criarNota} />
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <Indicadores notas={notas} />

        <section className="panel p-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_repeat(3,minmax(0,1fr))_auto] lg:items-end">
            <div className="grid gap-2">
              <label
                htmlFor="busca"
                className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Pesquisar
              </label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="busca"
                  className="pl-9"
                  placeholder="Número da nota ou descrição"
                  value={busca}
                  onChange={(e) => setBusca(e.target.value)}
                />
              </div>
            </div>

            <Filtro
              id="f-maquina"
              rotulo="Máquina"
              valor={maquina}
              aoMudar={setMaquina}
              opcoes={MAQUINAS}
              rotuloTodos="Todas as máquinas"
            />
            <Filtro
              id="f-prioridade"
              rotulo="Prioridade"
              valor={prioridade}
              aoMudar={setPrioridade}
              opcoes={PRIORIDADES}
              rotuloTodos="Todas as prioridades"
            />
            <Filtro
              id="f-status"
              rotulo="Status"
              valor={status}
              aoMudar={setStatus}
              opcoes={STATUS_LIST}
              rotuloTodos="Todos os status"
            />

            <Button variant="outline" onClick={limpar} className="lg:mb-0">
              Limpar filtros
            </Button>
          </div>
        </section>

        <TabelaNotas notas={filtradas} />
        <Graficos notas={filtradas} />
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        Dados fictícios para demonstração — Painel de Manutenção Industrial
      </footer>
    </div>
  );
}

function Filtro({
  id,
  rotulo,
  valor,
  aoMudar,
  opcoes,
  rotuloTodos,
}: {
  id: string;
  rotulo: string;
  valor: string;
  aoMudar: (v: string) => void;
  opcoes: readonly string[];
  rotuloTodos: string;
}) {
  return (
    <div className="grid gap-2">
      <label
        htmlFor={id}
        className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
      >
        {rotulo}
      </label>
      <Select value={valor} onValueChange={aoMudar}>
        <SelectTrigger id={id}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={TODOS}>{rotuloTodos}</SelectItem>
          {opcoes.map((o) => (
            <SelectItem key={o} value={o}>
              {o}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
