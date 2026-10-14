{{- define "valuation.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "valuation.fullname" -}}
{{- if .Values.fullnameOverride }}{{ .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}{{- else }}{{ printf "%s-%s" .Release.Name (include "valuation.name" .) | trunc 63 | trimSuffix "-" }}{{- end }}
{{- end }}
{{- define "valuation.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "valuation.labels" -}}
helm.sh/chart: {{ include "valuation.chart" . }}
{{ include "valuation.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
{{- define "valuation.selectorLabels" -}}
app.kubernetes.io/name: {{ include "valuation.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
{{- define "valuation.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}{{ default (include "valuation.fullname" .) .Values.serviceAccount.name }}{{- else }}{{ default "default" .Values.serviceAccount.name }}{{- end }}
{{- end }}
