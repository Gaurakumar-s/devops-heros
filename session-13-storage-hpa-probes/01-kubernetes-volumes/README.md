# Kubernetes Volumes

What I learned from running `01-volumes/`, `02-persistent-storage/` and `03-storageclass/` on minikube. The screenshots of each run are in `../Submission.md`.

## Why volumes exist
A container's filesystem is a throwaway overlay. When the container restarts, every file written inside it is gone. A volume is a directory that lives *outside* the container filesystem and is mounted into it, so data can outlive a container restart, a Pod restart, or even the Pod itself, depending on the volume type.

```text
            lifetime of the data
emptyDir    = Pod                     (dies with the Pod)
hostPath    = node                    (survives the Pod, tied to one node)
PV / PVC    = cluster resource        (survives Pods, nodes, reschedules)
```

---

## emptyDir
An empty directory created when the Pod is scheduled, deleted when the Pod is removed. Shared by all containers in the Pod.

```yaml
volumes:
  - name: app-storage
    emptyDir: {}            # add `medium: Memory` for a tmpfs
containers:
  - name: app
    volumeMounts:
      - name: app-storage
        mountPath: /data
```

What I observed (`emptydir-pod.yaml`):
- wrote `/data/note.txt`, then killed PID 1 in the container → the container restarted (`RESTARTS 1`) and the file was **still there**: emptyDir survives container restarts.
- `kubectl delete pod` + re-apply → `/data` was empty again: emptyDir does **not** survive Pod deletion.

Use it for scratch space, caches, and sharing files between a main container and a sidecar.

---

## hostPath
Mounts a directory from the **node's** filesystem into the Pod.

```yaml
volumes:
  - name: host-storage
    hostPath:
      path: /tmp/hostpath-data
      type: DirectoryOrCreate
```

What I observed (`hostpath-pod.yaml`):
- wrote `/data/host.txt`, deleted the Pod, re-created it → the file was still there.
- `minikube ssh -- cat /tmp/hostpath-data/host.txt` shows the same file on the node.

Caveats: the data is on *one* node, so if the Pod is rescheduled elsewhere it will not find it; it also lets a Pod read/write the host, which is a security concern. Fine for single-node minikube labs and for DaemonSets that need node logs; not for application data in a real cluster.

---

## PersistentVolume (PV)
A cluster-level piece of storage, created by an admin (or by a provisioner). It is not namespaced and it is independent of any Pod.

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: student-pv
spec:
  capacity:
    storage: 1Gi
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain   # keep data when the claim is deleted
  hostPath:
    path: /tmp/student-data
```

Key fields:
- `capacity` – how much it offers.
- `accessModes` – `ReadWriteOnce` (one node), `ReadOnlyMany`, `ReadWriteMany` (needs NFS/CephFS-type storage), `ReadWriteOncePod`.
- `persistentVolumeReclaimPolicy` – `Retain` keeps the data and leaves the PV `Released`; `Delete` removes the backing storage when the PVC is deleted (default for dynamically provisioned PVs).
- Status goes `Available` → `Bound` → `Released`.

---

## PersistentVolumeClaim (PVC)
A namespaced *request* for storage made by an application. Kubernetes finds (or creates) a PV that satisfies it and binds the two one-to-one.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: student-pvc
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 500Mi
```

Pods never reference a PV directly; they reference the claim:

```yaml
volumes:
  - name: persistent-storage
    persistentVolumeClaim:
      claimName: student-pvc
```

What I observed (`02-persistent-storage/`):
- wrote `Student: Gaurav Kumar` to `/data/student-data.txt`, deleted the Pod, re-created it → the file was still there. The storage belongs to the claim, not to the Pod.
- `kubectl describe pvc` shows `Used By: storage-demo`, which is also why a PVC in use cannot be deleted immediately (it waits with a `kubernetes.io/pvc-protection` finalizer).
- One surprise: `student-pvc` did **not** bind to my hand-made `student-pv`. `kubectl get pvc` showed it bound to `pvc-ff93cca6-…` with STORAGECLASS `standard`, and `student-pv` stayed `Available`. Reason: minikube has a *default* StorageClass, so a PVC with no `storageClassName` is handled by the dynamic provisioner first. To force binding to the manual PV, set `storageClassName: ""` on both or give the PV and PVC a matching `storageClassName: manual`.

---

## StorageClass
Describes a *type* of storage and the provisioner that can create it on demand. It removes the need for an admin to pre-create PVs.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard
provisioner: k8s.io/minikube-hostpath      # on AWS: ebs.csi.aws.com, on GKE: pd.csi.storage.gke.io
reclaimPolicy: Delete
volumeBindingMode: Immediate              # or WaitForFirstConsumer
allowVolumeExpansion: false
```

On minikube:

```text
NAME                 PROVISIONER                RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION
standard (default)   k8s.io/minikube-hostpath   Delete          Immediate           false
```

- `(default)` – used by any PVC that does not name a class.
- `volumeBindingMode: WaitForFirstConsumer` delays creating the volume until a Pod is scheduled, so the disk is created in the same zone as the Pod (important on cloud providers).
- `parameters:` (not shown) pass provider options such as disk type (`gp3`), IOPS, encryption.

---

## Dynamic provisioning
With a StorageClass in place, the flow is:

```text
PVC (storageClassName: standard, 500Mi)
  │
  ▼
StorageClass "standard"  →  provisioner k8s.io/minikube-hostpath
  │
  ▼
PV "pvc-9da2b0cd-…" created automatically, 500Mi, Bound to default/dynamic-pvc
  │
  ▼
hostPath /tmp/hostpath-provisioner/default/dynamic-pvc on the node
```

What I observed (`03-storageclass/pvc.yaml`):
- 5 s after applying the PVC it was `Bound` and a PV named `pvc-<uuid>` existed that I never wrote.
- `kubectl describe pv` shows `StorageClass: standard`, `Reclaim Policy: Delete` and the real path on the node.
- Deleting the PVC deleted the PV too (`kubectl get pv` → `No resources found`) because of the `Delete` reclaim policy. With `Retain` the PV would stay in `Released` state and the data would still be on disk.

Static vs dynamic, in one line: *static* = admin creates PV, developer claims it; *dynamic* = developer claims, StorageClass creates the PV.

---

## Practical reference
```bash
kubectl get sc                                # storage classes, which is default
kubectl get pv                                # cluster-wide volumes and their status
kubectl get pvc -A                            # claims in every namespace
kubectl describe pvc <name>                   # events: why it is Pending, who uses it
kubectl get pv <name> -o jsonpath='{.spec.hostPath.path}'
kubectl patch sc standard -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'
```

Common "PVC stuck in Pending" causes: no default StorageClass and none named; no PV with enough capacity / matching access mode; `WaitForFirstConsumer` and no Pod scheduled yet; provisioner Pod not running (`kubectl get pods -n kube-system | grep provisioner`).
