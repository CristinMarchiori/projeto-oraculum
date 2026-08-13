import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Nota } from "@/lib/notas";
import { MAQUINAS, STATUS_LIST } from "@/lib/notas";

interface Props {
  notas: Nota[];
}

const CORES_STATUS = [
  "var(--status-aberta)",
  "var(--status-andamento)",
  "var(--status-concluida)",
];

export function Graficos({ notas }: Props) {
  const porMaquina = MAQUINAS.map((m) => ({
    maquina: m.replace(/\s\d+$/, ""),
    total: notas.filter((n) => n.maquina === m).length,
  }));

  const porStatus = STATUS_LIST.map((s) => ({
    name: s,
    value: notas.filter((n) => n.status === s).length,
  })).filter((d) => d.value > 0);

  return (
    <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="panel p-5">
        <h2 className="text-lg font-semibold text-foreground">Notas por máquina</h2>
        <p className="mb-4 text-sm text-muted-foreground">Volume de notas registradas por ativo</p>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={porMaquina} margin={{ top: 8, right: 8, bottom: 40, left: -20 }}>
              <XAxis
                dataKey="maquina"
                angle={-25}
                textAnchor="end"
                interval={0}
                tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                stroke="var(--border)"
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                stroke="var(--border)"
              />
              <Tooltip
                cursor={{ fill: "var(--muted)" }}
                contentStyle={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                formatter={(v: number) => [v, "Notas"]}
              />
              <Bar dataKey="total" fill="var(--primary)" radius={[4, 4, 0, 0]} maxBarSize={44} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="panel p-5">
        <h2 className="text-lg font-semibold text-foreground">Distribuição por status</h2>
        <p className="mb-4 text-sm text-muted-foreground">Participação de cada situação</p>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={porStatus}
                dataKey="value"
                nameKey="name"
                innerRadius={60}
                outerRadius={96}
                paddingAngle={2}
                stroke="var(--card)"
              >
                {porStatus.map((entry, i) => (
                  <Cell key={entry.name} fill={CORES_STATUS[i % CORES_STATUS.length]} />
                ))}
              </Pie>
              <Legend
                verticalAlign="bottom"
                iconType="circle"
                formatter={(value) => (
                  <span style={{ color: "var(--muted-foreground)", fontSize: 12 }}>{value}</span>
                )}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                formatter={(v: number, n: string) => [v, n]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}
