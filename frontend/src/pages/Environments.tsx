import { useState } from 'react';
import { EnvironmentSaveBody } from '../services/environments';
import { Environment } from '../types';
import { useEnvironments } from '../hooks/useEnvironments';
import { relTime } from '../utils/formatters';
import { Modal } from '../components/Modal';
import { Button, IconButton } from '../components/Button';
import {
  AlertCircle, Link, Mail, Key, Eye, EyeOff, CheckCircle2,
  Building2, Lock, AlertTriangle, Clock, Pencil, Trash2,
  Network, Plus, PlusCircle, Copy,
} from 'lucide-react';

function envDotColor(name: string): string {
  const n = name.toLowerCase();
  if (n.includes('prod')) return 'bg-success';
  if (n.includes('beta') || n.includes('staging') || n.includes('stage') || n.includes('dev')) return 'bg-warning';
  return 'bg-primary';
}

interface ModalProps {
  initial?: Environment;
  onClose: () => void;
  onSave: (data: EnvironmentSaveBody) => void;
  isPending: boolean;
  serverError: string;
}

function EnvironmentModal({ initial, onClose, onSave, isPending, serverError }: ModalProps) {
  const isEdit = !!initial;

  const [name,          setName]          = useState(initial?.name ?? '');
  const [baseUrl,       setBaseUrl]       = useState(initial?.baseUrl ?? '');
  const [description,   setDescription]   = useState(initial?.description ?? '');
  const [isActive,      setIsActive]      = useState(initial?.isActive ?? true);
  const [loginEmail,    setLoginEmail]    = useState(initial?.loginEmail ?? '');
  const [loginPassword, setLoginPassword] = useState('');
  const [showPassword,  setShowPassword]  = useState(false);

  const [nameError,     setNameError]     = useState('');
  const [urlError,      setUrlError]      = useState('');
  const [emailError,    setEmailError]    = useState('');
  const [passwordError, setPasswordError] = useState('');

  function validate(): boolean {
    let ok = true;
    if (!name.trim()) { setNameError('Name is required.'); ok = false; } else setNameError('');
    if (!baseUrl.startsWith('https://')) { setUrlError('Enter a valid URL starting with https://'); ok = false; } else setUrlError('');
    if (!loginEmail.trim()) { setEmailError('Login email is required.'); ok = false; } else setEmailError('');
    if (!isEdit && !loginPassword.trim()) { setPasswordError('Password is required.'); ok = false; } else setPasswordError('');
    return ok;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    const body: EnvironmentSaveBody = {
      name: name.trim(),
      baseUrl: baseUrl.trim(),
      description: description.trim(),
      isActive,
      loginEmail: loginEmail.trim(),
    };
    if (loginPassword.trim()) body.loginPassword = loginPassword.trim();
    onSave(body);
  }

  const isFormValid =
    name.trim().length > 0 &&
    baseUrl.startsWith('https://') &&
    loginEmail.trim().length > 0 &&
    (isEdit || loginPassword.trim().length > 0);

  return (
    <Modal
      onClose={onClose}
      size="md"
      backdropClassName="bg-surface-sidebar/40 backdrop-blur-sm"
      cardClassName="max-h-[92vh] flex flex-col"
    >
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-primary/10 flex items-center justify-center">
              {isEdit
                ? <Pencil size={18} className="text-primary" />
                : <PlusCircle size={18} className="text-primary" />
              }
            </div>
            <h2 className="font-semibold text-text-primary">
              {isEdit ? 'Edit environment' : 'Add environment'}
            </h2>
          </div>
          <IconButton onClick={onClose} size={32}>
            <Plus size={20} className="rotate-45" />
          </IconButton>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto">
          <div className="px-6 py-5 space-y-5">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Name <span className="text-error">*</span>
              </label>
              <input
                autoFocus type="text" value={name}
                onChange={(e) => { setName(e.target.value); if (nameError) setNameError(''); }}
                placeholder="Production"
                className={`w-full border rounded-xl px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-surface-main focus:outline-none focus:ring-2 transition-colors ${
                  nameError ? 'border-error focus:ring-error/20 focus:border-error' : 'border-border-subtle focus:ring-primary/20 focus:border-primary/40'
                }`}
              />
              {nameError && (
                <p className="mt-1.5 text-xs text-error flex items-center gap-1">
                  <AlertCircle size={12} />{nameError}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Base URL <span className="text-error">*</span>
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-secondary">
                  <Link size={16} />
                </span>
                <input
                  type="text" value={baseUrl}
                  onChange={(e) => { setBaseUrl(e.target.value); if (urlError) setUrlError(''); }}
                  placeholder="https://app.example.com"
                  className={`w-full border rounded-xl pl-9 pr-3.5 py-2.5 text-sm font-mono-code text-text-primary placeholder:text-text-secondary placeholder:font-sans bg-surface-main focus:outline-none focus:ring-2 transition-colors ${
                    urlError ? 'border-error focus:ring-error/20 focus:border-error' : 'border-border-subtle focus:ring-primary/20 focus:border-primary/40'
                  }`}
                />
              </div>
              {urlError && (
                <p className="mt-1.5 text-xs text-error flex items-center gap-1">
                  <AlertCircle size={12} />{urlError}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Description
                <span className="ml-1.5 text-xs font-normal text-text-secondary">(optional)</span>
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe this environment…"
                rows={2}
                className="w-full border border-border-subtle rounded-xl px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-surface-main focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 resize-none transition-colors"
              />
            </div>

            <div className="border-t border-border-subtle pt-1">
              <div className="flex items-center gap-2 mb-4">
                <Lock size={16} className="text-text-secondary" />
                <p className="text-sm font-medium text-text-primary">Dashboard credentials</p>
              </div>
              <p className="text-xs text-text-secondary mb-4 -mt-2 leading-relaxed">
                Used to log in to the dashboard when running tests. Stored in the database.
              </p>

              <div className="mb-4">
                <label className="block text-sm font-medium text-text-primary mb-1.5">
                  Login email <span className="text-error">*</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-secondary">
                    <Mail size={16} />
                  </span>
                  <input
                    type="email" value={loginEmail}
                    onChange={(e) => { setLoginEmail(e.target.value); if (emailError) setEmailError(''); }}
                    placeholder="you@example.com"
                    className={`w-full border rounded-xl pl-9 pr-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-surface-main focus:outline-none focus:ring-2 transition-colors ${
                      emailError ? 'border-error focus:ring-error/20 focus:border-error' : 'border-border-subtle focus:ring-primary/20 focus:border-primary/40'
                    }`}
                  />
                </div>
                {emailError && (
                  <p className="mt-1.5 text-xs text-error flex items-center gap-1">
                    <AlertCircle size={12} />{emailError}
                  </p>
                )}
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-sm font-medium text-text-primary">
                    Password {!isEdit && <span className="text-error">*</span>}
                  </label>
                  {isEdit && initial?.hasPassword && !loginPassword && (
                    <span className="inline-flex items-center gap-1 text-xs text-success font-medium">
                      <CheckCircle2 size={13} />
                      Password saved — leave blank to keep
                    </span>
                  )}
                </div>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-secondary">
                    <Key size={16} />
                  </span>
                  <input
                    type={showPassword ? 'text' : 'password'} value={loginPassword}
                    onChange={(e) => { setLoginPassword(e.target.value); if (passwordError) setPasswordError(''); }}
                    placeholder={isEdit ? '••••••••' : 'Enter password'}
                    className={`w-full border rounded-xl pl-9 pr-10 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-surface-main focus:outline-none focus:ring-2 transition-colors ${
                      passwordError ? 'border-error focus:ring-error/20 focus:border-error' : 'border-border-subtle focus:ring-primary/20 focus:border-primary/40'
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {passwordError && (
                  <p className="mt-1.5 text-xs text-error flex items-center gap-1">
                    <AlertCircle size={12} />{passwordError}
                  </p>
                )}
              </div>

              {isEdit && (
                <div className="mt-4">
                  <label className="block text-sm font-medium text-text-primary mb-1.5">Publisher</label>
                  <div className="flex items-center gap-2 bg-surface-muted border border-border-subtle rounded-xl px-3.5 py-2.5">
                    <Building2 size={15} className="text-primary flex-shrink-0" />
                    <span className="text-xs text-text-primary">
                      {initial?.publisher || <span className="text-text-secondary italic">Not yet detected — will be set on first run</span>}
                    </span>
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-border-subtle" />

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-primary">Active</p>
                <p className="text-xs text-text-secondary mt-0.5">Only active environments appear in run dialogs</p>
              </div>
              <button
                type="button" role="switch" aria-checked={isActive}
                onClick={() => setIsActive((v) => !v)}
                className={`relative w-11 h-6 rounded-full transition-colors duration-200 flex-shrink-0 focus:outline-none focus:ring-2 focus:ring-primary/30 ${
                  isActive ? 'bg-primary' : 'bg-border-subtle'
                }`}
              >
                <span className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${isActive ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
            </div>

            {serverError && (
              <div className="flex items-start gap-2 bg-error/5 border border-error/20 rounded-xl px-3.5 py-3">
                <AlertCircle size={16} className="text-error flex-shrink-0 mt-0.5" />
                <p className="text-sm text-error">{serverError}</p>
              </div>
            )}
          </div>

          <div className="flex gap-3 px-6 py-4 border-t border-border-subtle flex-shrink-0 bg-surface-muted/30">
            <Button type="button" variant="secondary" onClick={onClose} className="flex-1">Cancel</Button>
            <Button type="submit" disabled={isPending || !isFormValid} className="flex-1">
              {isPending && <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
              {isEdit ? 'Save Changes' : 'Create environment'}
            </Button>
          </div>
        </form>
    </Modal>
  );
}

function DeleteConfirmModal({
  env, onClose, onConfirm, isPending,
}: {
  env: Environment;
  onClose: () => void;
  onConfirm: () => void;
  isPending: boolean;
}) {
  return (
    <Modal onClose={onClose} size="sm" backdropClassName="bg-surface-sidebar/40 backdrop-blur-sm">
      <div className="px-6 pt-6 pb-4">
          <div className="w-12 h-12 rounded-2xl bg-error/10 flex items-center justify-center mb-4">
            <Trash2 size={24} className="text-error" />
          </div>
          <h2 className="font-semibold text-text-primary mb-1.5">Delete environment?</h2>
          <p className="text-sm text-text-secondary leading-relaxed">
            <span className="font-medium text-text-primary">"{env.name}"</span> will be permanently
            deleted. Any test runs using this environment will also be removed.
          </p>
        </div>
        <div className="flex gap-3 px-6 pb-6">
          <Button variant="secondary" onClick={onClose} className="flex-1">Cancel</Button>
          <Button variant="danger" onClick={onConfirm} disabled={isPending} className="flex-1">
            {isPending && <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
            Delete
          </Button>
        </div>
    </Modal>
  );
}

function EnvironmentCard({
  env, onEdit, onDelete,
}: {
  env: Environment;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [copied, setCopied] = useState(false);

  function copyUrl() {
    navigator.clipboard.writeText(env.baseUrl).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const credentialsOk = env.loginEmail && env.hasPassword;

  return (
    <div className="bg-surface-main border border-border-subtle rounded-xl p-5 flex flex-col gap-4 hover:border-primary/30 hover:shadow-sm transition-all group">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 mt-0.5 ${envDotColor(env.name)}`} />
          <h3 className="font-semibold text-text-primary text-sm truncate">{env.name}</h3>
        </div>
        {env.isActive ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-success/10 border border-success/20 text-success text-xs font-semibold flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-success" />Active
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-muted border border-border-subtle text-text-secondary text-xs font-medium flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-border-subtle" />Inactive
          </span>
        )}
      </div>

      {env.description && (
        <p className="text-xs text-text-secondary leading-relaxed line-clamp-2 -mt-1">{env.description}</p>
      )}

      <div className="bg-surface-muted rounded-lg px-3 py-2 border border-border-subtle/50">
        <p className="text-[10px] font-semibold text-text-secondary uppercase tracking-wider mb-1">BASE URL</p>
        <button type="button" onClick={copyUrl} title={copied ? 'Copied!' : 'Click to copy'} className="group/url flex items-center justify-between gap-2 w-full">
          <code className="font-mono-code text-xs text-primary truncate text-left select-all">{env.baseUrl}</code>
          {copied
            ? <CheckCircle2 size={14} className="flex-shrink-0 text-success" />
            : <Copy size={14} className="flex-shrink-0 text-text-secondary group-hover/url:text-primary transition-colors" />
          }
        </button>
      </div>

      <div className={`rounded-lg px-3 py-2 border ${credentialsOk ? 'bg-surface-muted border-border-subtle/50' : 'bg-warning/5 border-warning/30'}`}>
        <p className="text-[10px] font-semibold text-text-secondary uppercase tracking-wider mb-1">CREDENTIALS</p>
        {credentialsOk ? (
          <div className="flex items-center gap-1.5">
            <Lock size={14} className="text-success" />
            <span className="text-xs text-text-primary truncate">{env.loginEmail}</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <AlertTriangle size={14} className="text-warning" />
            <span className="text-xs text-warning font-medium">Not configured — click Edit</span>
          </div>
        )}
      </div>

      <div className={`rounded-lg px-3 py-2 border ${env.publisher ? 'bg-surface-muted border-border-subtle/50' : 'bg-warning/5 border-warning/30'}`}>
        <p className="text-[10px] font-semibold text-text-secondary uppercase tracking-wider mb-1">PUBLISHER</p>
        {env.publisher ? (
          <div className="flex items-center gap-1.5">
            <Building2 size={14} className="text-primary" />
            <span className="text-xs text-text-primary truncate">{env.publisher}</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <AlertTriangle size={14} className="text-warning" />
            <span className="text-xs text-warning font-medium">Not set — click Edit</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-1.5 text-xs text-text-secondary">
        <Clock size={16} />
        Created: {relTime(env.createdAt)}
      </div>

      <div className="mt-auto pt-3 border-t border-border-subtle flex justify-end gap-2">
        <button onClick={onEdit} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-text-secondary hover:text-primary hover:bg-primary/10 transition-colors">
          <Pencil size={15} />Edit
        </button>
        <button onClick={onDelete} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-error hover:bg-error/10 transition-colors">
          <Trash2 size={15} />Delete
        </button>
      </div>
    </div>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 px-8 text-center">
      <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-5">
        <Network size={30} className="text-primary" />
      </div>
      <h2 className="text-base font-semibold text-text-primary mb-2">No environments yet</h2>
      <p className="text-sm text-text-secondary max-w-xs mb-6 leading-relaxed">
        Each environment holds a base URL and login credentials for the dashboard under test.
      </p>
      <Button onClick={onCreate}>
        <Plus size={18} />
        Add Environment
      </Button>
    </div>
  );
}

export default function Environments() {
  const {
    environments, isLoading,
    modal, serverError,
    createMutation, updateMutation, deleteMutation,
    openCreate, openEdit, openDelete, closeModal,
  } = useEnvironments();

  return (
    <div className="p-8 max-w-7xl">

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Environments</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Each environment has its own base URL and login credentials. Tests run under the environment you select.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus size={18} />
          Add Environment
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-52 bg-surface-muted rounded-xl animate-pulse" />
          ))}
        </div>
      ) : environments.length === 0 ? (
        <EmptyState onCreate={openCreate} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {environments.map((env) => (
            <EnvironmentCard
              key={env.id}
              env={env}
              onEdit={() => openEdit(env)}
              onDelete={() => openDelete(env)}
            />
          ))}

          <button
            onClick={openCreate}
            className="rounded-xl border-2 border-dashed border-border-subtle p-5 flex flex-col items-center justify-center gap-2 min-h-[180px] hover:border-primary/40 hover:bg-primary/5 transition-all group"
          >
            <div className="w-10 h-10 rounded-xl bg-surface-muted group-hover:bg-primary/10 flex items-center justify-center transition-colors">
              <Plus size={20} className="text-text-secondary group-hover:text-primary transition-colors" />
            </div>
            <span className="text-sm font-medium text-text-secondary group-hover:text-primary transition-colors">
              Add environment
            </span>
          </button>
        </div>
      )}

      {modal?.type === 'create' && (
        <EnvironmentModal
          onClose={closeModal}
          onSave={(body) => createMutation.mutate(body)}
          isPending={createMutation.isPending}
          serverError={serverError}
        />
      )}

      {modal?.type === 'edit' && (
        <EnvironmentModal
          initial={modal.env}
          onClose={closeModal}
          onSave={(body) => updateMutation.mutate({ id: modal.env.id, body })}
          isPending={updateMutation.isPending}
          serverError={serverError}
        />
      )}

      {modal?.type === 'delete' && (
        <DeleteConfirmModal
          env={modal.env}
          onClose={closeModal}
          onConfirm={() => deleteMutation.mutate(modal.env.id)}
          isPending={deleteMutation.isPending}
        />
      )}
    </div>
  );
}
