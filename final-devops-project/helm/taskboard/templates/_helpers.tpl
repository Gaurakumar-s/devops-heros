{{- define "taskboard.name" -}}{{ .Chart.Name }}{{- end -}}
{{- define "taskboard.fullname" -}}{{ .Release.Name }}-{{ .Chart.Name }}{{- end -}}
{{- define "taskboard.labels" -}}
app.kubernetes.io/name: {{ include "taskboard.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
{{- define "taskboard.selectorLabels" -}}
app.kubernetes.io/name: {{ include "taskboard.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
