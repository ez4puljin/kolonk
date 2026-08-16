import { useMemo, useState } from "react";
import { Archive, Download, FolderCog, HardDrive, RotateCcw, TriangleAlert } from "lucide-react";

import { api, errorMessage } from "../../api/client";
import {
  useBackupDirectory,
  useBackups,
  useCreateBackupMutation,
  useRestoreBackupMutation,
  useSetBackupDirectoryMutation,
} from "../../api/queries/system";
import type { BackupFile } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { t } from "../../i18n/mn";
import { formatBytes, formatDateTime } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { TextField } from "../catalog/_shared";

/** Сервер `filename` талбараар буцаадаг (DTO-д `name`) — хоёуланг нь дэмжинэ. */
type BackupRow = BackupFile;

function fileNameOf(row: BackupRow): string {
  return row.filename;
}

export function BackupPage() {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const [createOpen, setCreateOpen] = useState(false);
  const [restoreTarget, setRestoreTarget] = useState<BackupRow | null>(null);
  const [confirmWord, setConfirmWord] = useState("");
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const [dirOpen, setDirOpen] = useState(false);
  const [dirDraft, setDirDraft] = useState("");
  const [dirError, setDirError] = useState<string | null>(null);

  const backupsQuery = useBackups();
  const directoryQuery = useBackupDirectory();
  const createMutation = useCreateBackupMutation();
  const restoreMutation = useRestoreBackupMutation();
  const setDirMutation = useSetBackupDirectoryMutation();

  const directory = directoryQuery.data ?? null;

  const openDirEditor = (): void => {
    // Анхдагч хавтас үед хоосон эхэлнэ — хэрэглэгч өөрийн замаа бичнэ.
    setDirDraft(directory && !directory.is_default ? directory.directory : "");
    setDirError(null);
    setDirOpen(true);
  };

  const saveDirectory = (trimmed: string): void => {
    setDirError(null);
    setDirMutation.mutate(trimmed, {
      onSuccess: () => {
        toastSuccess(t.admin.backupDirSaved);
        setDirOpen(false);
      },
      onError: (error) => setDirError(errorMessage(error)),
    });
  };

  const rows = useMemo<BackupRow[]>(() => backupsQuery.data?.items ?? [], [backupsQuery.data]);

  const totals = useMemo(
    () => ({
      count: rows.length,
      bytes: rows.reduce((sum, row) => sum + (row.size_bytes ?? 0), 0),
      latest: rows[0]?.created_at ?? null,
    }),
    [rows],
  );

  const download = async (row: BackupRow): Promise<void> => {
    const name = fileNameOf(row);
    setDownloading(name);
    try {
      await api.download(`/api/backups/${encodeURIComponent(name)}/download`, undefined, name);
    } catch (error) {
      toastError(errorMessage(error));
    } finally {
      setDownloading(null);
    }
  };

  const createBackup = (): void => {
    createMutation.mutate(undefined, {
      onSuccess: () => {
        toastSuccess(t.admin.backupCreated_);
        setCreateOpen(false);
      },
      onError: (error) => {
        toastError(errorMessage(error));
        setCreateOpen(false);
      },
    });
  };

  const submitRestore = (): void => {
    if (!restoreTarget || confirmWord.trim().toUpperCase() !== t.admin.restoreWord) return;
    setRestoreError(null);
    restoreMutation.mutate(
      { name: fileNameOf(restoreTarget), confirm: t.admin.restoreWord },
      {
        onSuccess: () => {
          setRestoreTarget(null);
          setConfirmWord("");
          toastSuccess(t.common.saved);
        },
        onError: (error) => setRestoreError(errorMessage(error)),
      },
    );
  };

  const columns: Column<BackupRow>[] = [
    {
      key: "name",
      header: t.admin.backupFile,
      primary: true,
      render: (row) => <span className="num font-semibold break-all">{fileNameOf(row)}</span>,
    },
    {
      key: "created_at",
      header: t.admin.backupCreated,
      numeric: true,
      render: (row) => formatDateTime(row.created_at),
    },
    {
      key: "size",
      header: t.admin.backupSize,
      align: "right",
      numeric: true,
      render: (row) => formatBytes(row.size_bytes),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            variant="secondary"
            size="md"
            icon={<Download />}
            loading={downloading === fileNameOf(row)}
            onClick={() => void download(row)}
          >
            {t.admin.download}
          </Button>
          <Button
            variant="danger"
            size="md"
            icon={<RotateCcw />}
            onClick={() => {
              setRestoreTarget(row);
              setConfirmWord("");
              setRestoreError(null);
            }}
          >
            {t.admin.restore}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.admin.backup}
        subtitle={t.admin.backupSubtitle}
        actions={
          <Button
            variant="primary"
            size="lg"
            icon={<Archive />}
            loading={createMutation.isPending}
            onClick={() => setCreateOpen(true)}
          >
            {t.admin.createBackup}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.admin.backupCount} value={totals.count} tone="neutral" />
        <StatBox label={t.admin.backupSize} value={formatBytes(totals.bytes)} tone="action" />
        <StatBox
          label={t.admin.backupCreated}
          value={totals.latest ? formatDateTime(totals.latest) : "—"}
          tone="success"
        />
      </div>

      {/* Хадгалах хавтас — серверийн бүтэн зам */}
      <Card
        title={t.admin.backupDir}
        actions={
          <Button variant="secondary" size="md" icon={<FolderCog />} onClick={openDirEditor}>
            {t.admin.editPath}
          </Button>
        }
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <span className="num min-w-0 flex-1 break-all text-[15px] font-semibold text-ink">
            {directory ? directory.directory : "…"}
          </span>
          {directory ? (
            <span className="flex items-center gap-2 text-sm text-ink-soft">
              <HardDrive className="h-4 w-4" />
              {t.admin.backupDirFree}: <b className="num text-ink">{directory.free_mb} МБ</b>
            </span>
          ) : null}
          {directory?.is_default ? (
            <span className="rounded-full bg-surface-sunken px-3 py-1 text-xs font-semibold text-ink-soft">
              {t.admin.backupDirDefault}
            </span>
          ) : null}
        </div>
      </Card>

      <div className="flex items-start gap-4 rounded-xl border border-warning/30 bg-warning-soft px-5 py-4">
        <TriangleAlert className="mt-0.5 h-6 w-6 shrink-0 text-warning-dark" />
        <p className="text-[15px] font-medium text-warning-dark">{t.admin.restoreWarning}</p>
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => fileNameOf(row)}
          loading={backupsQuery.isLoading}
          empty={
            <EmptyState
              icon={<Archive className="h-7 w-7" />}
              title={t.common.empty}
              hint={t.common.emptyHint}
              action={
                <Button variant="primary" size="md" onClick={() => setCreateOpen(true)}>
                  {t.admin.createBackup}
                </Button>
              }
            />
          }
        />
      </Card>

      <ConfirmDialog
        open={createOpen}
        title={t.admin.createBackup}
        message={t.admin.createBackupConfirm}
        variant="primary"
        confirmLabel={t.admin.createBackup}
        loading={createMutation.isPending}
        onConfirm={createBackup}
        onCancel={() => setCreateOpen(false)}
      />

      <Modal
        open={dirOpen}
        onClose={() => setDirOpen(false)}
        size="md"
        title={t.admin.backupDir}
        dismissible={!setDirMutation.isPending}
        footer={
          <>
            <Button
              variant="secondary"
              size="md"
              disabled={setDirMutation.isPending}
              onClick={() => saveDirectory("")}
            >
              {t.admin.useDefaultPath}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={dirDraft.trim() === ""}
              loading={setDirMutation.isPending}
              onClick={() => saveDirectory(dirDraft.trim())}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField
            label={t.admin.backupDir}
            value={dirDraft}
            onChange={setDirDraft}
            placeholder="D:\Kolonk\backups"
            hint={t.admin.backupDirHint}
          />
          {dirError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {dirError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={restoreTarget !== null}
        onClose={() => setRestoreTarget(null)}
        size="md"
        title={t.admin.restore}
        subtitle={restoreTarget ? fileNameOf(restoreTarget) : ""}
        dismissible={!restoreMutation.isPending}
        footer={
          <>
            <Button
              variant="secondary"
              size="md"
              disabled={restoreMutation.isPending}
              onClick={() => setRestoreTarget(null)}
            >
              {t.common.cancel}
            </Button>
            <Button
              variant="danger"
              size="md"
              disabled={confirmWord.trim().toUpperCase() !== t.admin.restoreWord}
              loading={restoreMutation.isPending}
              onClick={submitRestore}
            >
              {t.admin.restore}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="flex items-start gap-4 rounded-xl border border-danger/30 bg-danger-soft px-4 py-3">
            <TriangleAlert className="mt-0.5 h-6 w-6 shrink-0 text-danger-dark" />
            <p className="text-[15px] font-semibold text-danger-dark">{t.admin.restoreWarning}</p>
          </div>
          <TextField
            label={t.admin.restoreConfirm}
            value={confirmWord}
            onChange={setConfirmWord}
            placeholder={t.admin.restoreWord}
            hint={`${t.common.confirm}: ${t.admin.restoreWord}`}
          />
          {restoreError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {restoreError}
            </p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}

export default BackupPage;
