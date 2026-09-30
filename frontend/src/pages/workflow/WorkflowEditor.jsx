import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Controls, MiniMap, MarkerType,
  addEdge, useNodesState, useEdgesState, useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from '@dagrejs/dagre';
import { Save, Play, Square, ArrowLeft, Plus, LayoutGrid, History, Loader2, Settings2 } from 'lucide-react';
import { workflowAPI, executionAPI, llmAPI, schedulerAPI, errMsg } from '../../utils/api';
import { Spinner, useToast, pick } from '../../components/ui';
import BaseNode, { RunContext } from './BaseNode';
import Inspector from './Inspector';
import NodePicker from './NodePicker';
import ExecutionPanel, { nodeLogInfo } from './ExecutionPanel';
import { NODES, getDef, defaultData } from './nodeRegistry';

const nodeTypes = Object.fromEntries(Object.keys(NODES).map((k) => [k, BaseNode]));
const FIRST_START = () => ({ id: 'start_1', type: 'start', position: { x: 80, y: 160 }, data: defaultData('start') });
const edgeDefaults = { type: 'default', markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#9aa1b0' }, style: { stroke: '#9aa1b0', strokeWidth: 2 } };
const ALIAS = { http: 'http_request' };
const isActive = (s) => ['running', 'pending', 'queued'].includes(s);
const normStatus = (s) => String(s || '').toLowerCase().replace('executionstatus.', '');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const uid = () => `node_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

function Editor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const rf = useReactFlow();
  const wrapRef = useRef(null);
  const [toast, notify] = useToast();

  const [workflow, setWorkflow] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [connections, setConnections] = useState([]);
  const [runStatus, setRunStatus] = useState({});
  const [runLogs, setRunLogs] = useState([]);
  const [running, setRunning] = useState(false);
  const [panel, setPanel] = useState(null); // null | 'run' | 'history'
  const [history, setHistory] = useState([]);
  const [selectedExec, setSelectedExec] = useState(null);
  const [currentExec, setCurrentExec] = useState(null); // id of the run that is executing now
  const [stopping, setStopping] = useState(false);
  const pollToken = useRef(0);
  useEffect(() => () => { pollToken.current += 1; }, []); // stop polling when leaving the page

  const selected = nodes.find((n) => n.selected);
  const markDirty = () => setDirty(true);

  // ---------- load ----------
  useEffect(() => {
    (async () => {
      try {
        const { data: wf } = await workflowAPI.getById(id);
        setWorkflow(wf);
        setNodes((wf.workflow_json?.nodes || []).map((n) => ({ ...n, type: NODES[ALIAS[n.type] || n.type] ? (ALIAS[n.type] || n.type) : 'noop', data: n.data || {} })));
        setEdges((wf.workflow_json?.edges || []).map((e) => ({ ...edgeDefaults, ...e })));
      } catch (e) { notify(errMsg(e, 'Failed to load workflow'), 'error'); }
      finally { setLoading(false); }
      setNodes((nds) => { if (nds.length) return nds; setDirty(true); return [FIRST_START()]; });
      llmAPI.list().then((r) => setConnections(r.data || [])).catch(() => {});
    })();
  }, [id]); // eslint-disable-line

  // ---------- graph editing ----------
  const onConnect = useCallback((c) => { setEdges((eds) => addEdge({ ...c, ...edgeDefaults }, eds)); markDirty(); }, [setEdges]);

  const addNode = useCallback((type, position) => {
    if (type === 'start' && nodes.some((n) => n.type === 'start')) return notify('Only one Start node is allowed', 'error');
    const pos = position || rf.screenToFlowPosition({ x: window.innerWidth / 2 - 100, y: window.innerHeight / 2 - 60 });
    const nn = { id: uid(), type, position: pos, data: defaultData(type), selected: true };
    setNodes((nds) => [...nds.map((n) => ({ ...n, selected: false })), nn]);
    markDirty();
  }, [rf, setNodes, nodes, notify]);

  const onDrop = (e) => {
    e.preventDefault();
    const type = e.dataTransfer.getData('application/wf-node');
    if (type) addNode(type, rf.screenToFlowPosition({ x: e.clientX, y: e.clientY }));
  };

  const updateNode = useCallback((nid, field, value) => {
    setNodes((nds) => nds.map((n) => (n.id === nid ? { ...n, data: { ...n.data, [field]: value } } : n)));
    markDirty();
  }, [setNodes]);

  const deleteNode = (nid) => { setNodes((n) => n.filter((x) => x.id !== nid)); setEdges((e) => e.filter((x) => x.source !== nid && x.target !== nid)); markDirty(); };
  const duplicateNode = (nid) => {
    const n = nodes.find((x) => x.id === nid); if (!n) return;
    setNodes((nds) => [...nds.map((x) => ({ ...x, selected: false })), { ...n, id: uid(), selected: true, position: { x: n.position.x + 40, y: n.position.y + 60 }, data: structuredClone(n.data) }]);
    markDirty();
  };

  const autoLayout = () => {
    const g = new dagre.graphlib.Graph(); g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: 'LR', nodesep: 60, ranksep: 110 });
    nodes.forEach((n) => g.setNode(n.id, { width: 90, height: 90 }));
    edges.forEach((e) => g.setEdge(e.source, e.target));
    dagre.layout(g);
    setNodes((nds) => nds.map((n) => { const p = g.node(n.id); return { ...n, position: { x: p.x - 45, y: p.y - 45 } }; }));
    markDirty(); setTimeout(() => rf.fitView({ padding: 0.3, duration: 300 }), 50);
  };

  // ---------- save ----------
  const save = useCallback(async (silent) => {
    if (!workflow) return false;
    setSaving(true);
    try {
      const cleanNodes = nodes.map(({ id: nid, type, position, data }) => ({ id: nid, type, position, data }));
      const cleanEdges = edges.map(({ id: eid, source, target, sourceHandle, targetHandle }) => ({ id: eid, source, target, sourceHandle, targetHandle }));
      await workflowAPI.update(id, { name: workflow.name, description: workflow.description });
      await workflowAPI.save(id, cleanNodes, cleanEdges);
      // keep Scheduler in sync with the Schedule Trigger node
      const start = nodes.find((n) => n.type === 'start');
      if (start?.data?.triggerType === 'schedule' && start.data.cron) {
        await schedulerAPI.upsert(id, { cron: start.data.cron, enabled: start.data.enabled !== false })
          .catch((e) => notify(`Saved, but schedule sync failed: ${errMsg(e)}`, 'error'));
      } else {
        schedulerAPI.getByWorkflow(id).then((r) => r.data?.enabled && schedulerAPI.patch(r.data.id, { enabled: false })).catch(() => {});
      }
      setDirty(false);
      if (!silent) notify('Workflow saved');
      return true;
    } catch (e) { notify(errMsg(e, 'Failed to save'), 'error'); return false; }
    finally { setSaving(false); }
  }, [workflow, nodes, edges, id, notify]);

  useEffect(() => {
    const h = (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); save(); } };
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h);
  }, [save]);

  // ---------- execution ----------
  const applyLogs = (logs) => {
    setRunLogs(logs);
    const map = {};
    logs.forEach((l) => { const x = nodeLogInfo(l); if (x.nodeId) if (x.status !== 'skipped') map[x.nodeId] = { status: ['failed', 'error', 'cancelled'].includes(x.status) ? 'error' : x.status === 'running' ? 'running' : 'success', output: x.output }; });
    setRunStatus(map);
  };

  const loadHistory = async () => {
    try { const r = await executionAPI.list(id, { limit: 30 }); setHistory(r.data?.data || []); return r.data?.data || []; }
    catch { return []; }
  };

  const execute = async () => {
    if (!nodes.some((n) => n.type === 'start')) return notify('Add a Start node first', 'error');
    if (dirty && !(await save(true))) return;
    const token = ++pollToken.current;
    setRunning(true); setStopping(false); setPanel('run'); setRunLogs([]); setRunStatus({});
    try {
      const res = await executionAPI.execute(id);          // returns immediately; the run continues on the server
      const execId = res.data?.execution_id;
      if (!execId) throw new Error('Backend did not return an execution id');
      setCurrentExec(execId); setSelectedExec(execId);

      let status = 'running', fails = 0;
      while (token === pollToken.current) {                 // poll for live progress
        try {
          const [ex, nr] = await Promise.all([executionAPI.get(id, execId), executionAPI.nodes(id, execId).catch(() => null)]);
          status = normStatus((ex.data?.data || ex.data)?.status);
          applyLogs(nr?.data?.data || []);
          fails = 0;
        } catch (e) { if (++fails > 4) throw e; }          // tolerate brief network hiccups
        if (!isActive(status)) break;
        await sleep(1000);
      }
      if (token !== pollToken.current) return;              // page closed or a newer run started
      loadHistory();
      notify(status === 'cancelled' ? 'Execution stopped' : `Execution ${status}`, ['failed', 'partial', 'cancelled'].includes(status) ? 'error' : 'success');
    } catch (e) {
      if (token !== pollToken.current) return;
      setRunStatus({}); notify(errMsg(e, 'Execution failed'), 'error');
      setRunLogs([{ node_id: 'workflow', node_type: 'workflow', status: 'failed', error_message: errMsg(e) }]);
      loadHistory();
    } finally {
      if (token === pollToken.current) { setRunning(false); setStopping(false); setCurrentExec(null); }
    }
  };

  const stop = async () => {
    if (!currentExec || stopping) return;
    setStopping(true);
    try { await executionAPI.cancel(id, currentExec); notify('Stopping…'); }   // polling loop picks up the "cancelled" status
    catch (e) { notify(errMsg(e, 'Could not stop execution'), 'error'); setStopping(false); }
  };

  const openHistory = () => { setPanel('history'); loadHistory(); };
  const selectExec = async (e) => {
    setSelectedExec(e.id);
    try { const r = await executionAPI.nodes(id, e.id); applyLogs(r.data?.data || []); setPanel('run'); } catch (er) { notify(errMsg(er), 'error'); }
  };
  const cancelExec = async (e) => { try { await executionAPI.cancel(id, e.id); notify('Execution cancelled'); loadHistory(); } catch (er) { notify(errMsg(er), 'error'); } };
  const deleteExec = async (e) => { try { await executionAPI.remove(id, e.id); setHistory((h) => h.filter((x) => x.id !== e.id)); } catch (er) { notify(errMsg(er), 'error'); } };

  const ctx = useMemo(() => runStatus, [runStatus]);
  if (loading) return <Spinner label="Loading workflow…" />;
  if (!workflow) return <div className="center-msg">Workflow not found</div>;

  return (
    <div className="wf-editor">
      <div className="wf-topbar">
        <button className="icon-btn" onClick={() => navigate('/workflows')} title="Back"><ArrowLeft size={18} /></button>
        <input className="wf-name" value={workflow.name || ''} onChange={(e) => { setWorkflow({ ...workflow, name: e.target.value }); markDirty(); }} placeholder="Workflow name" />
        <span className={`dirty ${dirty ? 'on' : ''}`}>{dirty ? 'Unsaved changes' : 'Saved'}</span>
        <div className="grow" />
        <div className="pop-wrap">
          <button className="icon-btn" title="Workflow settings" onClick={() => setSettingsOpen(!settingsOpen)}><Settings2 size={17} /></button>
          {settingsOpen && (
            <div className="pop">
              <label>Description</label>
              <textarea className="input" rows="3" value={workflow.description || ''} onChange={(e) => { setWorkflow({ ...workflow, description: e.target.value }); markDirty(); }} placeholder="What does this workflow do?" />
            </div>
          )}
        </div>
        <button className="btn btn-ghost" onClick={autoLayout}><LayoutGrid size={15} />Tidy up</button>
        <button className="btn btn-ghost" onClick={openHistory}><History size={15} />Executions</button>
        <button className="btn btn-outline" onClick={() => save()} disabled={saving}>{saving ? <Loader2 size={15} className="spin" /> : <Save size={15} />}Save</button>
        {running ? (
          <button className="btn btn-stop" onClick={stop} disabled={stopping || !currentExec}>
            {stopping ? <Loader2 size={15} className="spin" /> : <Square size={15} />}{stopping ? 'Stopping…' : 'Stop'}
          </button>
        ) : (
          <button className="btn btn-primary" onClick={execute}><Play size={15} />Execute workflow</button>
        )}
      </div>

      <div className="wf-canvas" ref={wrapRef} onDrop={onDrop} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }}>
        <RunContext.Provider value={ctx}>
          <ReactFlow
            nodes={nodes} edges={edges} nodeTypes={nodeTypes} defaultEdgeOptions={edgeDefaults}
            onNodesChange={(c) => { onNodesChange(c); if (c.some((x) => x.type !== 'select' && x.type !== 'dimensions')) markDirty(); }}
            onEdgesChange={(c) => { onEdgesChange(c); if (c.some((x) => x.type === 'remove')) markDirty(); }}
            onConnect={onConnect} fitView fitViewOptions={{ padding: 0.4, maxZoom: 1 }} deleteKeyCode={['Backspace', 'Delete']}
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1.4} color="#d5d8e0" />
            <Controls showInteractive={false} position="bottom-left" />
            <MiniMap pannable zoomable position="bottom-right" nodeColor={(n) => getDef(n.type).color} maskColor="rgba(240,242,246,.7)" />
          </ReactFlow>
        </RunContext.Provider>
        {nodes.length === 0 && (
          <button className="wf-empty" onClick={() => setPickerOpen(true)}><Plus size={28} /><span>Add first step…</span></button>
        )}
        <button className="wf-add" onClick={() => setPickerOpen(true)} title="Add node"><Plus size={20} /></button>
      </div>

      {pickerOpen && <NodePicker onClose={() => setPickerOpen(false)} onPick={(t) => { addNode(t); }} />}
      {selected && !pickerOpen && (
        <Inspector key={selected.id} node={selected} connections={connections} output={runStatus[selected.id]?.output}
          onChange={updateNode} onDelete={deleteNode} onDuplicate={duplicateNode}
          onClose={() => setNodes((nds) => nds.map((n) => ({ ...n, selected: false })))} />
      )}
      {panel && <ExecutionPanel tab={panel} setTab={(t) => { setPanel(t); if (t === 'history') loadHistory(); }} logs={runLogs} running={running}
        history={history} selectedId={selectedExec} onSelect={selectExec} onRefresh={loadHistory} onCancel={cancelExec} onDelete={deleteExec} onClose={() => setPanel(null)} />}
      {toast}
    </div>
  );
}

export default function WorkflowEditor() {
  return <ReactFlowProvider><Editor /></ReactFlowProvider>;
}
