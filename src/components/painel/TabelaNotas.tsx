import type { Nota } from "@/lib/notas";
import { formatarData } from "@/lib/notas";
import { EtiquetaPrioridade, EtiquetaStatus } from "./Etiquetas";

interface Props {
  notas: Nota[];
}

export function TabelaNotas({ notas }: Props) {
  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="text-lg font-semibold text-foreground">Notas de manutenção</h2>
        <span className="text-sm text-muted-foreground">{notas.length} registro(s)</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] border-collapse text-sm">
          <thead>
            <tr className="bg-secondary text-left">
              {[
                "Número",
                "Máquina",
                "Descrição",
                "Responsável",
                "Prioridade",
                "Status",
                "Abertura",
              ].map((h) => (
                <th
                  key={h}
                  className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-secondary-foreground"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {notas.map((n) => (
              <tr key={n.id} className="border-t border-border transition-colors hover:bg-muted/60">
                <td className="px-5 py-3 font-semibold text-primary whitespace-nowrap">
                  {n.numero}
                </td>
                <td className="px-5 py-3 whitespace-nowrap text-foreground">{n.maquina}</td>
                <td className="max-w-[320px] px-5 py-3 text-muted-foreground">{n.descricao}</td>
                <td className="px-5 py-3 whitespace-nowrap text-foreground">{n.responsavel}</td>
                <td className="px-5 py-3">
                  <EtiquetaPrioridade prioridade={n.prioridade} />
                </td>
                <td className="px-5 py-3">
                  <EtiquetaStatus status={n.status} />
                </td>
                <td className="px-5 py-3 whitespace-nowrap text-muted-foreground">
                  {formatarData(n.dataAbertura)}
                </td>
              </tr>
            ))}
            {notas.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-muted-foreground">
                  Nenhuma nota encontrada com os filtros aplicados.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
