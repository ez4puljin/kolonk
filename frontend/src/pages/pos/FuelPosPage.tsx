import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Droplets, Gauge, ShoppingBasket, Wifi, WifiOff } from "lucide-react";

import { usePumps } from "../../api/queries/pumps";
import { useCurrentShift } from "../../api/queries/shifts";
import type { LitersStr, Pump, PumpNozzle, UUID } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { AmountLiterToggle, type EntryMode } from "../../components/pos/AmountLiterToggle";
import { NozzlePicker } from "../../components/pos/NozzlePicker";
import { NumPadModal } from "../../components/pos/NumPadModal";
import { PumpGrid } from "../../components/pos/PumpGrid";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { t } from "../../i18n/mn";
import { PRESET_AMOUNTS, PRESET_LITERS } from "../../lib/constants";
import { dCmp, dDiv, dMul, dToQty } from "../../lib/decimal";
import { formatLiters, formatMNT, formatNumber } from "../../lib/format";
import { useCartStore } from "../../stores/cart";
import { useFuelSaleStore } from "../../stores/fuelSale";
import { usePumpsStore } from "../../stores/pumps";
import { useUiStore } from "../../stores/ui";

const NUMPAD_ENTRY = "fuel.entry";

/** Литрийг 3 орноор — савны хөдөлгөөнтэй ижил нарийвчлал. */
function litersOf(value: string): LitersStr {
  const raw = value.trim();
  return raw === "" ? "0" : raw;
}

export function FuelPosPage() {
  const navigate = useNavigate();

  const { data: current, isLoading: shiftLoading } = useCurrentShift();
  const { data: pumpsPage, isLoading: pumpsLoading } = usePumps({ active_only: true });
  const telemetry = usePumpsStore((state) => state.telemetry);
  const connection = usePumpsStore((state) => state.connection);

  const sale = useFuelSaleStore();
  const cartLines = useCartStore((state) => state.lines);
  const cartTotal = useCartStore((state) => state.total);
  const openNumPad = useUiStore((state) => state.openNumPad);

  const [selectedPumpId, setSelectedPumpId] = useState<UUID | null>(null);
  const [entryMode, setEntryMode] = useState<EntryMode>("amount");
  /** Кассын гараар оруулсан утга — горимоос хамаарч литр эсвэл ₮. */
  const [entry, setEntry] = useState("");

  const pumps = useMemo(() => pumpsPage?.items ?? [], [pumpsPage]);
  const selectedPump = useMemo(
    () => pumps.find((pump) => pump.id === selectedPumpId) ?? null,
    [pumps, selectedPumpId],
  );

  const shiftOpen = Boolean(current?.shift);

  // Насосны таталт дуусмагц төлбөрийн дэлгэц рүү. Гар бүртгэлд түгээгч
  // "Төлбөр рүү" эсвэл "Бараа нэмэх" гэдгээ өөрөө сонгоно.
  useEffect(() => {
    if (sale.phase === "awaiting_payment" && sale.authorizationId !== null) {
      navigate("/pos/payment");
    }
  }, [sale.phase, sale.authorizationId, navigate]);

  // Ээлж хаагдвал эхлүүлсэн урсгалыг цэвэрлэнэ.
  useEffect(() => {
    if (!shiftOpen && !shiftLoading) setSelectedPumpId(null);
  }, [shiftOpen, shiftLoading]);

  const closePanel = (): void => {
    setSelectedPumpId(null);
    setEntry("");
    sale.reset();
  };

  const handleSelectPump = (pump: Pump): void => {
    setSelectedPumpId(pump.id);
    setEntry("");
    sale.reset();
    // Ганц хошуутай насосны түлш нэг мөсөн тодорхой — шууд сонгоно.
    if (pump.nozzles.length === 1) selectNozzle(pump, pump.nozzles[0]);
  };

  const selectNozzle = (pump: Pump, nozzle: PumpNozzle): void => {
    sale.selectNozzle({
      pumpId: pump.id,
      pumpNumber: pump.number,
      nozzleId: nozzle.id,
      nozzleNumber: nozzle.nozzle_number,
      fuelId: nozzle.fuel_id,
      fuelName: nozzle.fuel_name,
      fuelColor: nozzle.color_hex,
      tankId: nozzle.tank_id,
      unitPrice: nozzle.price_per_liter,
    });
  };

  const openEntryPad = (): void => {
    openNumPad({
      target: NUMPAD_ENTRY,
      title: entryMode === "liters" ? t.pos.presetLiters : t.pos.presetAmount,
      value: entry,
      allowDecimal: true,
      suffix: entryMode === "liters" ? t.units.liter : t.units.mnt,
    });
  };

  const handleNumPad = (target: string, value: string): void => {
    if (target !== NUMPAD_ENTRY) return;
    setEntry(value.trim());
  };

  const unitPrice = sale.unitPrice ?? "0";

  /** Оруулсан утгаас нөгөөг нь тооцоолно: литр ⇄ дүн. */
  const computed = useMemo(() => {
    if (entry === "" || dCmp(entry, "0") <= 0 || dCmp(unitPrice, "0") <= 0) {
      return { liters: "0", amount: "0.00" };
    }
    if (entryMode === "liters") {
      return { liters: litersOf(entry), amount: dMul(unitPrice, dToQty(entry)) };
    }
    // Мөнгөөр: литр = дүн / нэгж үнэ (3 орон).
    return { liters: dDiv(entry, unitPrice, 3), amount: entry };
  }, [entry, entryMode, unitPrice]);

  const canSell =
    selectedPump !== null &&
    sale.nozzleId !== null &&
    dCmp(computed.liters, "0") > 0 &&
    dCmp(computed.amount, "0") > 0;

  /**
   * Насос жолоодохгүй — тооцоолсон литр, дүнгээр борлуулалтад бүртгэнэ.
   *
   * `next` нь дараагийн алхмыг заана: шууд төлбөр рүү, эсвэл нэг борлуулалтад
   * бараа нэмэхээр дэлгүүр рүү (түлшний мөр сагстай хамт төлөгдөнө).
   */
  const handleSell = (next: "payment" | "store"): void => {
    if (!canSell) return;
    sale.manual(computed.liters, computed.amount, entryMode);
    navigate(next === "store" ? "/pos/store" : "/pos/payment");
  };

  // ---------------------------------------------------------------- Ээлжгүй
  if (!shiftLoading && !shiftOpen) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title={t.pos.title} />
        <div className="flex flex-1 items-center justify-center">
          <div className="flex w-full max-w-lg flex-col items-center gap-6 rounded-2xl border-2 border-warning bg-warning-soft px-6 py-12 text-center">
            <span className="flex h-20 w-20 items-center justify-center rounded-full bg-warning text-white">
              <Gauge className="h-10 w-10" />
            </span>
            <div className="space-y-2">
              <h2 className="text-2xl font-bold text-ink">{t.shift.noOpen}</h2>
              <p className="text-ink-soft">{t.pos.noOpenShift}</p>
            </div>
            <Button variant="warning" size="lg" onClick={() => navigate("/shift")} className="min-w-56">
              {t.pos.openShiftNow}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ------------------------------------------------------- Насос сонгосон үе
  if (selectedPump) {
    const nozzle = selectedPump.nozzles.find((item) => item.id === sale.nozzleId) ?? null;

    return (
      <div className="flex flex-1 flex-col gap-5">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={closePanel}
            className="flex h-12 items-center gap-2 rounded-xl border border-line-strong bg-white px-4 font-semibold text-ink active:bg-surface-sunken"
          >
            <ChevronLeft className="h-5 w-5" />
            {t.pos.forecourt}
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-2xl font-bold text-ink">
              {t.pumps.pumpNo}
              {selectedPump.number} · {selectedPump.name}
            </h1>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <div className="flex flex-col gap-5">
            <NozzlePicker
              nozzles={selectedPump.nozzles}
              value={sale.nozzleId}
              onChange={(picked) => {
                selectNozzle(selectedPump, picked);
                setEntry("");
              }}
            />

            {nozzle ? (
              <AmountLiterToggle
                value={entryMode}
                onChange={(mode) => {
                  setEntryMode(mode);
                  setEntry("");
                }}
              />
            ) : null}
          </div>

          <div className="flex flex-col gap-5">
            {nozzle ? (
              <>
                {/* Гараар оруулах талбар — дарахад тоон гар нээгдэнэ */}
                <button
                  type="button"
                  onClick={openEntryPad}
                  className="flex min-h-28 w-full flex-col justify-center gap-1 rounded-2xl border-2 border-line-strong bg-surface-alt px-6 py-4 text-left active:bg-surface-sunken"
                >
                  <span className="text-sm font-semibold tracking-wide text-ink-soft uppercase">
                    {entryMode === "liters" ? t.pos.presetLiters : t.pos.presetAmount}
                  </span>
                  <span className="num text-[48px] leading-none font-black text-ink">
                    {entry === ""
                      ? "0"
                      : entryMode === "liters"
                        ? `${formatNumber(entry, 2)} ${t.units.liter}`
                        : formatMNT(entry)}
                  </span>
                </button>

                {/* Түргэн сонголт */}
                <div className="grid grid-cols-4 gap-2">
                  {(entryMode === "liters" ? PRESET_LITERS : PRESET_AMOUNTS).map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setEntry(String(value))}
                      className="num h-14 rounded-xl border-2 border-line-strong bg-white text-[15px] font-bold text-ink active:bg-surface-sunken"
                    >
                      {entryMode === "liters" ? `${value}${t.units.liter}` : formatNumber(value, 0)}
                    </button>
                  ))}
                </div>

                {/* Автомат тооцоо — нөгөө талын утга */}
                <div className="rounded-2xl border border-line-strong bg-white px-5 py-4">
                  <div className="num flex items-baseline justify-between gap-3">
                    <span className="text-sm font-semibold tracking-wide text-ink-soft uppercase">
                      {entryMode === "liters" ? t.common.amount : t.pos.liters}
                    </span>
                    <span className="text-[40px] leading-none font-black text-success-dark">
                      {entryMode === "liters"
                        ? formatMNT(computed.amount)
                        : `${formatLiters(computed.liters, 2)}`}
                    </span>
                  </div>
                  <div className="num mt-2 text-sm text-ink-soft">
                    {/* t.units.perLiter аль хэдийн "₮/л" тул formatMNT биш
                        formatNumber ашиглана — эс бөгөөс "2 990₮ ₮/л" болно. */}
                    {nozzle.fuel_name} · {formatNumber(nozzle.price_per_liter)} {t.units.perLiter}
                  </div>
                </div>

                {sale.error ? (
                  <div className="rounded-xl border border-danger bg-danger-soft px-4 py-3 text-[15px] font-semibold text-danger-dark">
                    {sale.error}
                  </div>
                ) : null}

                {/* Нэг борлуулалтад бараа нэмэх — түлш сагстай хамт төлөгдөнө */}
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Button
                    variant="secondary"
                    size="lg"
                    icon={<ShoppingBasket />}
                    disabled={!canSell}
                    onClick={() => handleSell("store")}
                  >
                    {t.pos.addGoods}
                  </Button>
                  <Button
                    variant="success"
                    size="lg"
                    disabled={!canSell}
                    onClick={() => handleSell("payment")}
                  >
                    {t.pos.toPayment}
                  </Button>
                </div>
              </>
            ) : (
              <EmptyState title={t.pos.selectNozzle} hint={t.pos.selectFuel} />
            )}
          </div>
        </div>

        <NumPadModal onSubmit={handleNumPad} />
      </div>
    );
  }

  // --------------------------------------------------------------- Талбай
  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={t.pos.forecourt}
        subtitle={
          current?.shift ? (
            <span className="num">
              {t.shift.number}
              {current.shift.number} · {formatMNT(current.sales.gross_total)} · {current.sales.count}{" "}
              {t.common.rows}
            </span>
          ) : undefined
        }
        actions={
          <>
            <Button
              variant="secondary"
              size="lg"
              icon={<ShoppingBasket />}
              onClick={() => navigate("/pos/store")}
            >
              {t.pos.store}
              {cartLines.length > 0 ? ` · ${formatMNT(cartTotal())}` : ""}
            </Button>
            <span
              className={`inline-flex h-12 items-center gap-2 rounded-xl border px-4 text-sm font-semibold ${
                connection === "online"
                  ? "border-success/40 bg-success-soft text-success-dark"
                  : "border-warning/40 bg-warning-soft text-warning-dark"
              }`}
            >
              {connection === "online" ? <Wifi className="h-5 w-5" /> : <WifiOff className="h-5 w-5" />}
              {connection === "online" ? t.common.online : t.common.reconnecting}
            </span>
          </>
        }
      />

      <PumpGrid
        pumps={pumps}
        telemetry={telemetry}
        onSelect={handleSelectPump}
        loading={pumpsLoading}
        disabled={!shiftOpen}
        extra={
          // Задлан зарах бүтээгдэхүүн — насостой ижил плиткаар талбайд байрлана.
          <button
            type="button"
            disabled={!shiftOpen}
            onClick={() => navigate("/pos/bulk")}
            className="flex min-h-44 flex-col justify-between gap-3 rounded-2xl border-2 border-dashed border-action bg-action-soft/25 px-4 py-4 text-left transition-colors hover:bg-action-soft/50 active:bg-action-soft disabled:pointer-events-none disabled:opacity-40"
          >
            <span className="flex items-center gap-3">
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-action text-white">
                <Droplets className="h-7 w-7" />
              </span>
              <span className="text-xl leading-snug font-bold text-ink">{t.pos.bulkProducts}</span>
            </span>
            <span className="text-[15px] font-semibold text-ink-soft">{t.pos.bulkHint}</span>
          </button>
        }
      />
    </div>
  );
}

export default FuelPosPage;
