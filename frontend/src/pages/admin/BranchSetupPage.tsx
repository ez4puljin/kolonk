/**
 * Салбарын тохиргоо — нэг салбарын бүх тохируулга нэг дэлгэцэнд.
 *
 * Таб: Ерөнхий (нэр, хаяг) · Түгээгчид · Сав · Насос.
 * Насосыг талбай дахь бодит байршлаар нь торон дээр байрлуулж, хошуу бүрд
 * ямар түлш, аль савнаас авахыг заана — ПОС яг энэ зохион байгуулалтаар
 * харагдана.
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  CreditCard,
  Database,
  Fuel,
  Gauge,
  Plus,
  Settings2,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  useBranchPaymentMethods,
  useBranches,
  useSetBranchPaymentMethodsMutation,
  useUpdateBranchMutation,
} from "../../api/queries/branches";
import { useFuels } from "../../api/queries/fuels";
import {
  useCreateNozzleMutation,
  useCreatePumpMutation,
  useDeleteNozzleMutation,
  useDeletePumpMutation,
  usePumps,
  useUpdateNozzleMutation,
  useUpdatePumpMutation,
} from "../../api/queries/pumps";
import { useCreateTankMutation, useTanks, useUpdateTankMutation } from "../../api/queries/tanks";
import { useCreateUserMutation, useRoles, useUsers } from "../../api/queries/users";
import type { Pump, PumpNozzle, Tank, UUID } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { InitialsAvatar } from "../../components/ui/InitialsAvatar";
import { Modal } from "../../components/ui/Modal";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TabBar } from "../../components/ui/TabBar";
import { t } from "../../i18n/mn";
import { dToNumber } from "../../lib/decimal";
import { formatLiters, formatMNT } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { NumberField, PickerField, TextField, ToggleField } from "../catalog/_shared";

type Tab = "general" | "cashiers" | "tanks" | "pumps" | "payments";

/** Талбайн торны хэмжээ — насосыг байрлуулах нүднүүд. */
const GRID_COLS = 4;
const GRID_ROWS = 4;

export function BranchSetupPage() {
  const { branchId = "" } = useParams();
  const navigate = useNavigate();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const [tab, setTab] = useState<Tab>("general");

  const branchesQuery = useBranches();
  const branch = (branchesQuery.data ?? []).find((item) => item.id === branchId) ?? null;

  const tanksQuery = useTanks({ branch_id: branchId as UUID });
  const pumpsQuery = usePumps({ branch_id: branchId as UUID });
  const fuelsQuery = useFuels({ active_only: true });
  const usersQuery = useUsers({ limit: 200 });
  const rolesQuery = useRoles();

  const updateBranch = useUpdateBranchMutation();
  const createTank = useCreateTankMutation();
  const updateTank = useUpdateTankMutation();
  const createPump = useCreatePumpMutation();
  const updatePump = useUpdatePumpMutation();
  const deletePump = useDeletePumpMutation();
  const createNozzle = useCreateNozzleMutation();
  const updateNozzle = useUpdateNozzleMutation();
  const deleteNozzle = useDeleteNozzleMutation();
  const createUser = useCreateUserMutation();
  const paymentsQuery = useBranchPaymentMethods(branchId as UUID);
  const setPayments = useSetBranchPaymentMethodsMutation();

  const tanks = useMemo(() => tanksQuery.data?.items ?? [], [tanksQuery.data]);
  const pumps = useMemo(() => pumpsQuery.data?.items ?? [], [pumpsQuery.data]);
  const fuels = useMemo(() => fuelsQuery.data?.items ?? [], [fuelsQuery.data]);
  const cashiers = useMemo(
    () => (usersQuery.data?.items ?? []).filter((user) => user.branch_id === branchId),
    [usersQuery.data, branchId],
  );

  // ---------------- Төлбөрийн хэрэгсэл ----------------
  /** Хадгалахаас өмнөх төлөв — унтраасныг шууд харуулна. */
  const [payDraft, setPayDraft] = useState<Record<string, boolean> | null>(null);

  const paymentRows = useMemo(() => paymentsQuery.data ?? [], [paymentsQuery.data]);
  const payValue = (method: string, fallback: boolean): boolean =>
    payDraft?.[method] ?? fallback;

  const togglePayment = (method: string, next: boolean): void => {
    setPayDraft((prev) => {
      const base = prev ?? Object.fromEntries(paymentRows.map((r) => [r.method, r.is_enabled]));
      return { ...base, [method]: next };
    });
  };

  const savePayments = (): void => {
    setPayments.mutate(
      {
        branchId: branchId as UUID,
        methods: paymentRows.map((row) => ({
          method: String(row.method),
          is_enabled: payValue(String(row.method), row.is_enabled),
        })),
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setPayDraft(null);
        },
        onError: (error) => toastError(errorMessage(error)),
      },
    );
  };

  // ---------------- Ерөнхий ----------------
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [active, setActive] = useState(true);
  const [requireMile, setRequireMile] = useState(true);
  const [requirePhoto, setRequirePhoto] = useState(true);

  useEffect(() => {
    if (!branch) return;
    setName(branch.name);
    setAddress(branch.address ?? "");
    setPhone(branch.phone ?? "");
    setActive(branch.is_active);
    setRequireMile(branch.require_open_mile);
    setRequirePhoto(branch.require_open_photo);
  }, [branch]);

  const saveGeneral = (): void => {
    updateBranch.mutate(
      {
        id: branchId as UUID,
        name: name.trim(),
        address: address.trim() || null,
        phone: phone.trim() || null,
        is_active: active,
        require_open_mile: requireMile,
        require_open_photo: requirePhoto,
      },
      {
        onSuccess: () => toastSuccess(t.common.saved),
        onError: (error) => toastError(errorMessage(error)),
      },
    );
  };

  // ---------------- Сав ----------------
  const [tankOpen, setTankOpen] = useState(false);
  const [editTank, setEditTank] = useState<Tank | null>(null);
  const [tankName, setTankName] = useState("");
  const [tankFuel, setTankFuel] = useState("");
  const [tankCapacity, setTankCapacity] = useState("");
  const [tankMin, setTankMin] = useState("");
  const [tankActive, setTankActive] = useState(true);
  const [tankError, setTankError] = useState<string | null>(null);

  const openTank = (tank: Tank | null): void => {
    setEditTank(tank);
    setTankError(null);
    setTankName(tank?.name ?? "");
    setTankFuel(tank?.fuel_id ?? fuels[0]?.id ?? "");
    setTankCapacity(tank?.capacity_l ?? "");
    setTankMin(tank?.min_level_l ?? "");
    setTankActive(tank?.is_active ?? true);
    setTankOpen(true);
  };

  const submitTank = (): void => {
    setTankError(null);
    const onSuccess = (): void => {
      toastSuccess(t.common.saved);
      setTankOpen(false);
    };
    const onError = (error: unknown): void => setTankError(errorMessage(error));

    if (editTank) {
      updateTank.mutate(
        {
          id: editTank.id,
          payload: {
            name: tankName.trim(),
            capacity_l: tankCapacity,
            min_level_l: tankMin || "0",
            is_active: tankActive,
          },
        },
        { onSuccess, onError },
      );
    } else {
      createTank.mutate(
        {
          branch_id: branchId as UUID,
          name: tankName.trim(),
          fuel_id: tankFuel as UUID,
          capacity_l: tankCapacity,
          min_level_l: tankMin || "0",
          is_active: tankActive,
        },
        { onSuccess, onError },
      );
    }
  };

  // ---------------- Насос ----------------
  const [pumpOpen, setPumpOpen] = useState(false);
  const [editPump, setEditPump] = useState<Pump | null>(null);
  const [pumpNumber, setPumpNumber] = useState("");
  const [pumpName, setPumpName] = useState("");
  const [pumpX, setPumpX] = useState(0);
  const [pumpY, setPumpY] = useState(0);
  const [pumpActive, setPumpActive] = useState(true);
  const [pumpError, setPumpError] = useState<string | null>(null);
  const [removePump, setRemovePump] = useState<Pump | null>(null);

  const nextNumber = useMemo(
    () => String(pumps.reduce((max, pump) => Math.max(max, pump.number), 0) + 1),
    [pumps],
  );

  /** Хамгийн эхний сул нүд — шинэ насосыг тэнд байрлуулна. */
  const firstFreeCell = useMemo(() => {
    const taken = new Set(pumps.map((pump) => `${pump.position_x},${pump.position_y}`));
    for (let y = 0; y < GRID_ROWS; y += 1) {
      for (let x = 0; x < GRID_COLS; x += 1) {
        if (!taken.has(`${x},${y}`)) return { x, y };
      }
    }
    return { x: 0, y: 0 };
  }, [pumps]);

  const openPump = (pump: Pump | null, cell?: { x: number; y: number }): void => {
    setEditPump(pump);
    setPumpError(null);
    setPumpNumber(pump ? String(pump.number) : nextNumber);
    setPumpName(pump?.name ?? "");
    setPumpX(pump?.position_x ?? cell?.x ?? firstFreeCell.x);
    setPumpY(pump?.position_y ?? cell?.y ?? firstFreeCell.y);
    setPumpActive(pump?.is_active ?? true);
    setPumpOpen(true);
  };

  const submitPump = (): void => {
    setPumpError(null);
    const onSuccess = (): void => {
      toastSuccess(t.common.saved);
      setPumpOpen(false);
    };
    const onError = (error: unknown): void => setPumpError(errorMessage(error));

    if (editPump) {
      updatePump.mutate(
        {
          id: editPump.id,
          payload: {
            number: Number(pumpNumber) || editPump.number,
            name: pumpName.trim(),
            position_x: pumpX,
            position_y: pumpY,
            is_active: pumpActive,
          },
        },
        { onSuccess, onError },
      );
    } else {
      createPump.mutate(
        {
          number: Number(pumpNumber) || 1,
          name: pumpName.trim() || `${t.pumps.pumpNo}${pumpNumber}`,
          branch_id: branchId as UUID,
          position_x: pumpX,
          position_y: pumpY,
          is_active: pumpActive,
        },
        { onSuccess, onError },
      );
    }
  };

  // ---------------- Хошуу ----------------
  const [nozzleOpen, setNozzleOpen] = useState(false);
  const [nozzlePump, setNozzlePump] = useState<Pump | null>(null);
  const [editNozzle, setEditNozzle] = useState<PumpNozzle | null>(null);
  const [nozzleNumber, setNozzleNumber] = useState("1");
  const [nozzleFuel, setNozzleFuel] = useState("");
  const [nozzleTank, setNozzleTank] = useState("");
  const [nozzleError, setNozzleError] = useState<string | null>(null);

  /** Сонгосон түлшний савнууд — хошуу зөвхөн ижил түлштэй савнаас авна. */
  const nozzleTankOptions = useMemo(
    () =>
      tanks
        .filter((tank) => tank.is_active && (nozzleFuel === "" || tank.fuel_id === nozzleFuel))
        .map((tank) => ({
          value: tank.id,
          label: tank.name,
          hint: `${formatLiters(tank.current_l, 0)} / ${formatLiters(tank.capacity_l, 0)}`,
        })),
    [tanks, nozzleFuel],
  );

  const openNozzle = (pump: Pump, nozzle: PumpNozzle | null): void => {
    setNozzlePump(pump);
    setEditNozzle(nozzle);
    setNozzleError(null);
    setNozzleNumber(
      nozzle ? String(nozzle.nozzle_number) : String(pump.nozzles.length + 1),
    );
    setNozzleFuel(nozzle?.fuel_id ?? fuels[0]?.id ?? "");
    setNozzleTank(nozzle?.tank_id ?? "");
    setNozzleOpen(true);
  };

  const submitNozzle = (): void => {
    if (!nozzlePump) return;
    setNozzleError(null);
    const onSuccess = (): void => {
      toastSuccess(t.common.saved);
      setNozzleOpen(false);
    };
    const onError = (error: unknown): void => setNozzleError(errorMessage(error));

    if (editNozzle) {
      updateNozzle.mutate(
        {
          pumpId: nozzlePump.id,
          nozzleId: editNozzle.id,
          payload: {
            nozzle_number: Number(nozzleNumber) || editNozzle.nozzle_number,
            fuel_id: nozzleFuel as UUID,
            tank_id: nozzleTank as UUID,
          },
        },
        { onSuccess, onError },
      );
    } else {
      createNozzle.mutate(
        {
          pumpId: nozzlePump.id,
          payload: {
            nozzle_number: Number(nozzleNumber) || 1,
            fuel_id: nozzleFuel as UUID,
            tank_id: nozzleTank as UUID,
          },
        },
        { onSuccess, onError },
      );
    }
  };

  // ---------------- Түгээгч ----------------
  const [cashierOpen, setCashierOpen] = useState(false);
  const [cashierName, setCashierName] = useState("");
  const [cashierUsername, setCashierUsername] = useState("");
  const [cashierPin, setCashierPin] = useState("");
  const [cashierPhone, setCashierPhone] = useState("");
  const [cashierError, setCashierError] = useState<string | null>(null);

  const cashierRoleId = useMemo(
    () => (rolesQuery.data?.items ?? []).find((role) => role.code === "cashier")?.id ?? "",
    [rolesQuery.data],
  );

  const submitCashier = (): void => {
    setCashierError(null);
    createUser.mutate(
      {
        username: cashierUsername.trim(),
        full_name: cashierName.trim(),
        pin: cashierPin.trim(),
        role_id: cashierRoleId as UUID,
        phone: cashierPhone.trim() || null,
        branch_id: branchId as UUID,
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setCashierOpen(false);
          setCashierName("");
          setCashierUsername("");
          setCashierPin("");
          setCashierPhone("");
        },
        onError: (error) => setCashierError(errorMessage(error)),
      },
    );
  };

  // ---------------- Багануудууд ----------------
  const tankColumns: Column<Tank>[] = [
    {
      key: "name",
      header: t.tanks.tank,
      primary: true,
      render: (row) => (
        <span className="flex items-center gap-3">
          <span
            className="h-9 w-2 shrink-0 rounded-full"
            style={{ backgroundColor: row.fuel.color_hex }}
          />
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-semibold text-ink">{row.name}</span>
            <span className="text-xs text-ink-soft">{row.fuel.name_mn}</span>
          </span>
        </span>
      ),
    },
    {
      key: "level",
      header: t.tanks.current,
      render: (row) => (
        <span className="flex min-w-[10rem] flex-col gap-1">
          <ProgressBar value={dToNumber(row.fill_pct)} autoTone />
          <span className="num text-xs text-ink-soft">
            {formatLiters(row.current_l, 0)} / {formatLiters(row.capacity_l, 0)}
          </span>
        </span>
      ),
    },
    {
      key: "min",
      header: t.tanks.minLevel,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatLiters(row.min_level_l, 0),
    },
    {
      key: "cost",
      header: t.tanks.avgCost,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.avg_cost),
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => (
        <StatusBadge
          size="sm"
          tone={row.is_active ? "success" : "neutral"}
          label={row.is_active ? t.common.active : t.common.inactive}
        />
      ),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <Button variant="secondary" size="md" onClick={() => openTank(row)}>
          {t.common.edit}
        </Button>
      ),
    },
  ];

  if (!branch) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title={t.branches.setup} back="/branches" />
        <EmptyState title={t.common.empty} hint={t.branches.empty} />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={`${branch.name} — ${t.branches.setup}`}
        subtitle={`${branch.code}${branch.address ? ` · ${branch.address}` : ""}`}
        back="/branches"
      >
        <TabBar<Tab>
          variant="underline"
          value={tab}
          onChange={setTab}
          items={[
            { value: "general", label: t.branches.tabGeneral, icon: <Settings2 className="h-5 w-5" /> },
            {
              value: "cashiers",
              label: t.branches.tabCashiers,
              icon: <Users className="h-5 w-5" />,
              badge: cashiers.length || null,
            },
            {
              value: "tanks",
              label: t.branches.tabTanks,
              icon: <Database className="h-5 w-5" />,
              badge: tanks.length || null,
            },
            {
              value: "pumps",
              label: t.branches.tabPumps,
              icon: <Gauge className="h-5 w-5" />,
              badge: pumps.length || null,
            },
            {
              value: "payments",
              label: t.branches.tabPayments,
              icon: <CreditCard className="h-5 w-5" />,
              badge: paymentRows.filter((row) => payValue(String(row.method), row.is_enabled)).length || null,
            },
          ]}
        />
      </PageHeader>

      {/* --- Ерөнхий --- */}
      {tab === "general" ? (
        <Card
          title={t.branches.tabGeneral}
          actions={
            <Button
              variant="primary"
              size="md"
              loading={updateBranch.isPending}
              disabled={name.trim() === ""}
              onClick={saveGeneral}
            >
              {t.common.save}
            </Button>
          }
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label={t.branches.name} value={name} onChange={setName} />
            <TextField label={t.branches.phone} value={phone} onChange={setPhone} />
            <div className="sm:col-span-2">
              <TextField label={t.branches.address} value={address} onChange={setAddress} />
            </div>
            <ToggleField label={t.branches.isActive} value={active} onChange={setActive} />
          </div>

          {/* Ээлж нээх журам — станц бүр өөр байдаг тул салбараар тохируулна. */}
          <div className="mt-5 flex flex-col gap-3 border-t border-line pt-5">
            <h3 className="text-sm font-bold tracking-wide text-ink-soft uppercase">
              {t.branches.shiftRules}
            </h3>
            <ToggleField
              label={t.branches.requireMile}
              hint={t.branches.requireMileHint}
              value={requireMile}
              onChange={setRequireMile}
            />
            <ToggleField
              label={t.branches.requirePhoto}
              hint={t.branches.requirePhotoHint}
              value={requirePhoto}
              onChange={setRequirePhoto}
            />
          </div>
        </Card>
      ) : null}

      {/* --- Түгээгчид --- */}
      {tab === "cashiers" ? (
        <Card
          title={t.branches.tabCashiers}
          actions={
            <Button
              variant="primary"
              size="md"
              icon={<UserPlus />}
              onClick={() => {
                setCashierError(null);
                setCashierOpen(true);
              }}
            >
              {t.branches.addCashier}
            </Button>
          }
          flush
        >
          {cashiers.length === 0 ? (
            <EmptyState
              icon={<Users className="h-7 w-7" />}
              title={t.branches.noCashiers}
              hint={t.common.emptyHint}
            />
          ) : (
            <ul className="flex flex-col divide-y divide-line">
              {cashiers.map((user) => (
                <li key={user.id} className="flex items-center gap-3 px-4 py-3">
                  <InitialsAvatar name={user.full_name} seed={user.id} />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate font-semibold text-ink">{user.full_name}</span>
                    <span className="num truncate text-xs text-ink-soft">
                      {user.username}
                      {user.phone ? ` · ${user.phone}` : ""}
                    </span>
                  </span>
                  <StatusBadge
                    size="sm"
                    tone={user.is_active ? "success" : "neutral"}
                    label={user.role_name_mn}
                  />
                </li>
              ))}
            </ul>
          )}
        </Card>
      ) : null}

      {/* --- Сав --- */}
      {tab === "tanks" ? (
        <Card
          title={t.branches.tabTanks}
          actions={
            <Button variant="primary" size="md" icon={<Plus />} onClick={() => openTank(null)}>
              {t.tanks.addTank}
            </Button>
          }
          flush
        >
          <DataTable
            columns={tankColumns}
            rows={tanks}
            rowKey={(row) => row.id}
            loading={tanksQuery.isLoading}
            empty={
              <EmptyState
                icon={<Database className="h-7 w-7" />}
                title={t.branches.noTanks}
                hint={t.common.emptyHint}
                action={
                  <Button variant="primary" size="md" onClick={() => openTank(null)}>
                    {t.tanks.addTank}
                  </Button>
                }
              />
            }
          />
        </Card>
      ) : null}

      {/* --- Насос: талбайн зураглал --- */}
      {tab === "pumps" ? (
        <div className="flex flex-col gap-6">
          <Card title={t.branches.forecourt} subtitle={t.branches.forecourtHint}>
            <div
              className="grid gap-3"
              style={{ gridTemplateColumns: `repeat(${GRID_COLS}, minmax(0, 1fr))` }}
            >
              {Array.from({ length: GRID_COLS * GRID_ROWS }, (_, index) => {
                const x = index % GRID_COLS;
                const y = Math.floor(index / GRID_COLS);
                const pump = pumps.find((item) => item.position_x === x && item.position_y === y);
                if (!pump) {
                  return (
                    <button
                      key={`${x}-${y}`}
                      type="button"
                      onClick={() => openPump(null, { x, y })}
                      className="flex min-h-24 items-center justify-center rounded-xl border-2 border-dashed border-line-strong text-ink-faint transition-colors hover:border-action hover:text-action"
                    >
                      <Plus className="h-5 w-5" />
                    </button>
                  );
                }
                return (
                  <button
                    key={pump.id}
                    type="button"
                    onClick={() => openPump(pump)}
                    className={[
                      "flex min-h-24 flex-col gap-1 rounded-xl border-2 px-3 py-2 text-left transition-colors",
                      pump.is_active
                        ? "border-action bg-action-soft/40 hover:bg-action-soft"
                        : "border-line-strong bg-surface-sunken",
                    ].join(" ")}
                  >
                    <span className="num text-lg font-black text-ink">
                      {t.pumps.pumpNo}
                      {pump.number}
                    </span>
                    <span className="truncate text-xs text-ink-soft">{pump.name}</span>
                    <span className="mt-auto flex flex-wrap gap-1">
                      {pump.nozzles.map((nozzle) => (
                        <span
                          key={nozzle.id}
                          className="rounded px-1.5 py-0.5 text-[11px] font-bold text-white"
                          style={{ backgroundColor: nozzle.color_hex }}
                        >
                          {nozzle.fuel_code}
                        </span>
                      ))}
                    </span>
                  </button>
                );
              })}
            </div>
          </Card>

          {/* Насос бүрийн хошуу — түлш ба сав */}
          {pumps.map((pump) => (
            <Card
              key={pump.id}
              title={`${t.pumps.pumpNo}${pump.number} · ${pump.name}`}
              subtitle={`${t.branches.position}: ${pump.position_x + 1}, ${pump.position_y + 1}`}
              actions={
                <>
                  <Button variant="secondary" size="md" icon={<Plus />} onClick={() => openNozzle(pump, null)}>
                    {t.pumps.addNozzle}
                  </Button>
                  <Button variant="ghost" size="md" onClick={() => openPump(pump)}>
                    {t.common.edit}
                  </Button>
                  <Button variant="ghost" size="md" icon={<Trash2 />} onClick={() => setRemovePump(pump)}>
                    {t.common.delete}
                  </Button>
                </>
              }
              flush
            >
              {pump.nozzles.length === 0 ? (
                <EmptyState compact title={t.branches.noNozzles} hint={t.branches.noNozzlesHint} />
              ) : (
                <ul className="flex flex-col divide-y divide-line">
                  {pump.nozzles.map((nozzle) => (
                    <li key={nozzle.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <span
                        className="num flex h-10 w-10 shrink-0 items-center justify-center rounded-lg font-black text-white"
                        style={{ backgroundColor: nozzle.color_hex }}
                      >
                        {nozzle.nozzle_number}
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="truncate font-semibold text-ink">{nozzle.fuel_name}</span>
                        <span className="num truncate text-xs text-ink-soft">
                          {t.tanks.tank}: {nozzle.tank_name} · {formatMNT(nozzle.price_per_liter)}
                          {t.units.perLiter}
                        </span>
                      </span>
                      <Button variant="secondary" size="md" onClick={() => openNozzle(pump, nozzle)}>
                        {t.common.edit}
                      </Button>
                      <Button
                        variant="ghost"
                        size="md"
                        icon={<Trash2 />}
                        onClick={() =>
                          deleteNozzle.mutate(
                            { pumpId: pump.id, nozzleId: nozzle.id },
                            {
                              onSuccess: () => toastSuccess(t.common.saved),
                              onError: (error) => toastError(errorMessage(error)),
                            },
                          )
                        }
                      />
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          ))}

          {pumps.length === 0 ? (
            <EmptyState
              icon={<Fuel className="h-7 w-7" />}
              title={t.branches.noPumps}
              hint={t.branches.forecourtHint}
            />
          ) : null}
        </div>
      ) : null}

      {/* --- Төлбөрийн хэрэгсэл --- */}
      {tab === "payments" ? (
        <Card
          title={t.branches.paymentMethods}
          subtitle={t.branches.paymentMethodsHint}
          actions={
            <Button
              variant="primary"
              size="md"
              disabled={payDraft === null}
              loading={setPayments.isPending}
              onClick={savePayments}
            >
              {t.common.save}
            </Button>
          }
        >
          <div className="flex flex-col gap-3">
            {paymentRows.map((row) => {
              const enabled = payValue(String(row.method), row.is_enabled);
              return (
                <ToggleField
                  key={String(row.method)}
                  label={row.label}
                  hint={row.locked ? t.branches.cashLocked : undefined}
                  value={enabled}
                  onChange={(next) => {
                    if (row.locked) return;
                    togglePayment(String(row.method), next);
                  }}
                />
              );
            })}
            {paymentRows.length === 0 ? (
              <EmptyState compact title={t.common.empty} hint={t.common.emptyHint} />
            ) : null}
          </div>
        </Card>
      ) : null}

      {/* ---------------- Цонхнууд ---------------- */}
      <Modal
        open={tankOpen}
        onClose={() => setTankOpen(false)}
        size="md"
        title={editTank ? t.tanks.editTank : t.tanks.addTank}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setTankOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={tankName.trim() === "" || tankFuel === "" || dToNumber(tankCapacity) <= 0}
              loading={createTank.isPending || updateTank.isPending}
              onClick={submitTank}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField label={t.tanks.tankName} value={tankName} onChange={setTankName} />
          <PickerField
            label={t.tanks.fuel}
            value={tankFuel}
            options={fuels.map((fuel) => ({ value: fuel.id, label: fuel.name_mn, hint: fuel.code }))}
            onChange={setTankFuel}
            disabled={editTank !== null}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              name="tank-capacity"
              label={t.tanks.capacity}
              value={tankCapacity}
              onChange={setTankCapacity}
              suffix={t.units.liter}
            />
            <NumberField
              name="tank-min"
              label={t.tanks.minLevel}
              value={tankMin}
              onChange={setTankMin}
              suffix={t.units.liter}
            />
          </div>
          <ToggleField label={t.common.active} value={tankActive} onChange={setTankActive} />
          {tankError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {tankError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={pumpOpen}
        onClose={() => setPumpOpen(false)}
        size="md"
        title={editPump ? t.pumps.editPump : t.pumps.addPump}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setPumpOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              loading={createPump.isPending || updatePump.isPending}
              onClick={submitPump}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              name="pump-number"
              label={t.pumps.pumpNo}
              value={pumpNumber}
              onChange={setPumpNumber}
              allowDecimal={false}
            />
            <TextField label={t.common.name} value={pumpName} onChange={setPumpName} />
          </div>

          {/* Байршил — торон дээр дарж сонгоно */}
          <div className="flex flex-col gap-1.5">
            <span className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">
              {t.branches.position}
            </span>
            <div
              className="grid gap-2"
              style={{ gridTemplateColumns: `repeat(${GRID_COLS}, minmax(0, 1fr))` }}
            >
              {Array.from({ length: GRID_COLS * GRID_ROWS }, (_, index) => {
                const x = index % GRID_COLS;
                const y = Math.floor(index / GRID_COLS);
                const taken = pumps.find(
                  (item) =>
                    item.position_x === x && item.position_y === y && item.id !== editPump?.id,
                );
                const selected = pumpX === x && pumpY === y;
                return (
                  <button
                    key={`${x}-${y}`}
                    type="button"
                    disabled={Boolean(taken)}
                    onClick={() => {
                      setPumpX(x);
                      setPumpY(y);
                    }}
                    className={[
                      "num flex h-12 items-center justify-center rounded-lg border-2 text-sm font-bold transition-colors",
                      selected
                        ? "border-action bg-action text-white"
                        : taken
                          ? "border-line-strong bg-surface-sunken text-ink-faint"
                          : "border-line-strong bg-white text-ink-soft hover:bg-surface-alt",
                    ].join(" ")}
                  >
                    {taken ? taken.number : ""}
                  </button>
                );
              })}
            </div>
          </div>

          <ToggleField label={t.common.active} value={pumpActive} onChange={setPumpActive} />
          {pumpError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {pumpError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={nozzleOpen}
        onClose={() => setNozzleOpen(false)}
        size="md"
        title={editNozzle ? t.pumps.editNozzle : t.pumps.addNozzle}
        subtitle={nozzlePump ? `${t.pumps.pumpNo}${nozzlePump.number} · ${nozzlePump.name}` : ""}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setNozzleOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={nozzleFuel === "" || nozzleTank === ""}
              loading={createNozzle.isPending || updateNozzle.isPending}
              onClick={submitNozzle}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <NumberField
            name="nozzle-number"
            label={t.pumps.nozzleNo}
            value={nozzleNumber}
            onChange={setNozzleNumber}
            allowDecimal={false}
          />
          <PickerField
            label={t.tanks.fuel}
            value={nozzleFuel}
            options={fuels.map((fuel) => ({ value: fuel.id, label: fuel.name_mn, hint: fuel.code }))}
            onChange={(value) => {
              setNozzleFuel(value);
              setNozzleTank("");
            }}
          />
          <PickerField
            label={t.branches.fromTank}
            value={nozzleTank}
            options={nozzleTankOptions}
            onChange={setNozzleTank}
            disabled={nozzleFuel === ""}
          />
          {nozzleTankOptions.length === 0 && nozzleFuel !== "" ? (
            <p className="rounded-xl bg-warning-soft px-4 py-3 text-sm font-medium text-warning-dark">
              {t.branches.noTankForFuel}
            </p>
          ) : null}
          {nozzleError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {nozzleError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={cashierOpen}
        onClose={() => setCashierOpen(false)}
        size="md"
        title={t.branches.addCashier}
        subtitle={branch.name}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setCashierOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={
                cashierName.trim() === "" || cashierUsername.trim() === "" || cashierPin.length < 4
              }
              loading={createUser.isPending}
              onClick={submitCashier}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField label={t.common.name} value={cashierName} onChange={setCashierName} />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label={t.admin.username} value={cashierUsername} onChange={setCashierUsername} />
            <TextField label={t.auth.pin} value={cashierPin} onChange={setCashierPin} />
          </div>
          <TextField label={t.common.phone} value={cashierPhone} onChange={setCashierPhone} />
          {cashierError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {cashierError}
            </p>
          ) : null}
        </div>
      </Modal>

      <ConfirmDialog
        open={removePump !== null}
        variant="danger"
        title={t.common.delete}
        message={removePump ? `${t.pumps.pumpNo}${removePump.number} · ${removePump.name}` : ""}
        confirmLabel={t.common.delete}
        loading={deletePump.isPending}
        onCancel={() => setRemovePump(null)}
        onConfirm={() => {
          if (!removePump) return;
          deletePump.mutate(removePump.id, {
            onSuccess: () => {
              toastSuccess(t.common.saved);
              setRemovePump(null);
            },
            onError: (error) => {
              toastError(errorMessage(error));
              setRemovePump(null);
            },
          });
        }}
      />

      <div className="no-print">
        <Button variant="ghost" size="md" onClick={() => navigate("/branches")}>
          {t.common.back}
        </Button>
      </div>
    </div>
  );
}

export default BranchSetupPage;
