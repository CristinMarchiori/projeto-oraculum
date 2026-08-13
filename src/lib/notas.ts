export type Prioridade = "Baixa" | "Média" | "Alta" | "Crítica";
export type Status = "Aberta" | "Em andamento" | "Concluída";

export interface Nota {
  id: string;
  numero: string;
  maquina: string;
  descricao: string;
  responsavel: string;
  prioridade: Prioridade;
  status: Status;
  dataAbertura: string; // ISO yyyy-mm-dd
}

export const MAQUINAS = [
  "Torno CNC 01",
  "Prensa Hidráulica 02",
  "Esteira Transportadora 03",
  "Compressor de Ar 04",
  "Fresadora 05",
  "Caldeira 06",
];

export const PRIORIDADES: Prioridade[] = ["Baixa", "Média", "Alta", "Crítica"];
export const STATUS_LIST: Status[] = ["Aberta", "Em andamento", "Concluída"];

export const NOTAS_INICIAIS: Nota[] = [
  {
    id: "1",
    numero: "NM-1001",
    maquina: "Torno CNC 01",
    descricao: "Ruído anormal no eixo principal durante usinagem",
    responsavel: "Carlos Andrade",
    prioridade: "Alta",
    status: "Em andamento",
    dataAbertura: "2026-07-28",
  },
  {
    id: "2",
    numero: "NM-1002",
    maquina: "Prensa Hidráulica 02",
    descricao: "Vazamento de óleo hidráulico na base do cilindro",
    responsavel: "Marina Souza",
    prioridade: "Crítica",
    status: "Aberta",
    dataAbertura: "2026-08-02",
  },
  {
    id: "3",
    numero: "NM-1003",
    maquina: "Esteira Transportadora 03",
    descricao: "Desalinhamento da correia transportadora",
    responsavel: "João Peixoto",
    prioridade: "Média",
    status: "Concluída",
    dataAbertura: "2026-07-15",
  },
  {
    id: "4",
    numero: "NM-1004",
    maquina: "Compressor de Ar 04",
    descricao: "Pressão abaixo do parâmetro operacional",
    responsavel: "Fernanda Lima",
    prioridade: "Alta",
    status: "Aberta",
    dataAbertura: "2026-08-05",
  },
  {
    id: "5",
    numero: "NM-1005",
    maquina: "Fresadora 05",
    descricao: "Substituição preventiva de rolamentos do fuso",
    responsavel: "Ricardo Alves",
    prioridade: "Baixa",
    status: "Concluída",
    dataAbertura: "2026-06-30",
  },
  {
    id: "6",
    numero: "NM-1006",
    maquina: "Caldeira 06",
    descricao: "Falha intermitente no sensor de temperatura",
    responsavel: "Patrícia Nunes",
    prioridade: "Crítica",
    status: "Em andamento",
    dataAbertura: "2026-08-08",
  },
  {
    id: "7",
    numero: "NM-1007",
    maquina: "Torno CNC 01",
    descricao: "Calibração do sistema de refrigeração",
    responsavel: "Carlos Andrade",
    prioridade: "Média",
    status: "Aberta",
    dataAbertura: "2026-08-10",
  },
  {
    id: "8",
    numero: "NM-1008",
    maquina: "Prensa Hidráulica 02",
    descricao: "Botoeira de emergência com contato falho",
    responsavel: "Marina Souza",
    prioridade: "Alta",
    status: "Concluída",
    dataAbertura: "2026-07-20",
  },
  {
    id: "9",
    numero: "NM-1009",
    maquina: "Esteira Transportadora 03",
    descricao: "Motorredutor com aquecimento excessivo",
    responsavel: "João Peixoto",
    prioridade: "Crítica",
    status: "Aberta",
    dataAbertura: "2026-08-11",
  },
  {
    id: "10",
    numero: "NM-1010",
    maquina: "Compressor de Ar 04",
    descricao: "Troca de filtro de ar e inspeção de mangueiras",
    responsavel: "Fernanda Lima",
    prioridade: "Baixa",
    status: "Em andamento",
    dataAbertura: "2026-08-03",
  },
  {
    id: "11",
    numero: "NM-1011",
    maquina: "Fresadora 05",
    descricao: "Painel elétrico com disjuntor desarmando",
    responsavel: "Ricardo Alves",
    prioridade: "Alta",
    status: "Aberta",
    dataAbertura: "2026-08-12",
  },
  {
    id: "12",
    numero: "NM-1012",
    maquina: "Caldeira 06",
    descricao: "Limpeza programada do trocador de calor",
    responsavel: "Patrícia Nunes",
    prioridade: "Média",
    status: "Concluída",
    dataAbertura: "2026-07-05",
  },
];

export function formatarData(iso: string) {
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
}
