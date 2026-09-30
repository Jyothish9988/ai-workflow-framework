import { memo, createContext, useContext, useEffect } from 'react';
import { Handle, Position, useUpdateNodeInternals } from '@xyflow/react';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { getDef, getOutputs } from './nodeRegistry';

/** nodeId -> { status, ... } — kept outside node.data so it never gets saved */
export const RunContext = createContext({});

function BaseNode({ id, type, data, selected }) {
  const def = getDef(type);
  const Icon = def.icon;
  const run = useContext(RunContext)[id];
  const outs = getOutputs(type, data);
  const update = useUpdateNodeInternals();
  const sig = outs.map((o) => o.id).join('|');
  useEffect(() => { update(id); }, [sig, id, update]);

  const cls = ['wfn', selected && 'is-selected', def.trigger && 'is-trigger', data?.disabled && 'is-disabled', run?.status && `run-${run.status}`]
    .filter(Boolean).join(' ');

  return (
    <div className={cls}>
      {!def.trigger && <Handle type="target" position={Position.Left} />}
      <div className="wfn-box" style={{ '--c': def.color }}>
        <Icon size={26} strokeWidth={1.8} />
        {run?.status && (
          <span className={`wfn-badge ${run.status}`}>
            {run.status === 'running' ? <Loader2 size={12} className="spin" /> : run.status === 'success' ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
          </span>
        )}
      </div>
      {outs.map((o, i) => {
        const top = `${((i + 1) * 100) / (outs.length + 1)}%`;
        return (
          <span key={o.id}>
            <Handle type="source" position={Position.Right} id={outs.length > 1 ? o.id : undefined} style={{ top }} />
            {outs.length > 1 && <span className="wfn-out-label" style={{ top }}>{o.label}</span>}
          </span>
        );
      })}
      <div className="wfn-label">
        <b>{data?.label || def.label}</b>
        <small>{def.summary?.(data || {})}</small>
      </div>
    </div>
  );
}

export default memo(BaseNode);
