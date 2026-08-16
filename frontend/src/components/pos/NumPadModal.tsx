import { Modal } from "../ui/Modal";
import { NumPad } from "../ui/NumPad";
import { t } from "../../i18n/mn";
import { useUiStore } from "../../stores/ui";

export interface NumPadModalProps {
  /** `(target, value)` — ui store-ийн `openNumPad({target})`-тай хослоно. */
  onSubmit: (target: string, value: string) => void;
  /** Тухайн талбарт тохирох түргэн дүнгүүд. */
  quickFor?: (target: string) => readonly number[] | undefined;
  submitLabel?: string;
}

/**
 * Тоо оруулах цорын ганц зам — ui store-оор дамжуулан нээгддэг NumPad цонх.
 *
 * Хуудас бүр нэг л удаа зурна: `useUiStore.openNumPad({ target: "..." })`
 * дуудсан үед автоматаар нээгдэж, батлахад `onSubmit(target, value)` дуудна.
 */
export function NumPadModal({ onSubmit, quickFor, submitLabel }: NumPadModalProps) {
  const numpad = useUiStore((state) => state.numpad);
  const setValue = useUiStore((state) => state.setNumPadValue);
  const close = useUiStore((state) => state.closeNumPad);

  if (!numpad) return null;

  const isLiters = numpad.suffix === t.units.liter;

  return (
    <Modal open onClose={close} size="sm" title={numpad.title}>
      <NumPad
        value={numpad.value}
        onChange={setValue}
        allowDecimal={numpad.allowDecimal}
        maxDecimals={isLiters ? 3 : 2}
        suffix={numpad.suffix}
        quick={quickFor?.(numpad.target)}
        submitLabel={submitLabel ?? t.common.confirm}
        onCancel={close}
        onSubmit={() => {
          const target = numpad.target;
          const value = numpad.value;
          close();
          onSubmit(target, value);
        }}
      />
    </Modal>
  );
}

export default NumPadModal;
