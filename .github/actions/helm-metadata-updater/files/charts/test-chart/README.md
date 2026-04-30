# Test Chart

The chart is used by the `doctest` module when running examples in the
`metadata-updater` script to test it.

## Parameters

### Global Parameters

Contains global parameters; these parameters are mirrored within the Telicent core umbrella chart.
Note: Only global parameters used within this chart will be listed below.

| Name                      | Description                                                                                                                     | Value   |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------- |
| `global.imageRegistry`    | Global image registry                                                                                                           | `""`    |
| `global.imagePullSecrets` | Global registry secret names as an array                                                                                        | `[]`    |
| `global.enterprise`       | Enable enterprise mode, adding additional features and configurations                                                           | `false` |
| `global.appHostDomain`    | Domain associated with Telicent application/ui services. This value cannot be changed after it is set                           | `""`    |
| `global.apiHostDomain`    | Domain associated with Telicent Api services. This value cannot be changed after it is set                                      | `""`    |
| `global.authHostDomain`   | Domain associated with Telicent authentication services, including OIDC providers. This value cannot be changed after it is set | `""`    |

### Application Parameters - UI and Secret

Contains parameters specific to the Graph User Interface.
Map functionality requires tokens and configuration defined within a secret.
It is recommended to store sensitive information including tokens/passwords in a Kubernetes secret and not in Helm values.
For Quick Start purposes, a secret named `tc-auth-gen-mapjs-graph-ui` will be created if one is not set.

| Name                         | Description                                                                                                        | Value                      |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------- |
| `ui.searchUiDeployed`        | If set to true, *Search UI* links will be available within *Graph UI*                                              | `true`                     |
| `ui.userPortalUiDeployed`    | If set to true, *User Portal UI* links will be available within *Graph UI*                                         | `true`                     |
| `ui.dataCatalogUiDeployed`   | If set to true, *Data Catalog UI* links will be available within *Graph UI*                                        | `true`                     |
| `ui.maptilerToken`           | The MapTiler token for the *Graph UI*                                                                              | `your.maptiler.token.here` |
| `ui.mapboxStyleSpecUrl`      | The Mapbox style spec URL for the *Graph UI* can be specified if using Mapbox styles                               | `""`                       |
| `ui.arcgisToken`             | The ArcGIS token for the *Graph UI* can be specified if using ArcGIS styles                                        | `""`                       |
| `ui.existingMapConfigSecret` | The name of an existing secret containing map configuration. See: '_mapjs.tpl' & 'secret-mapjs.yaml'               | `""`                       |
| `ui.mapV2Enabled`            | Whether to enable the new map implementation. MapV2 will eventually become the default and only map implementation | `false`                    |

### Application Parameters - OAuth

| Name             | Description                                   | Value                           |
| ---------------- | --------------------------------------------- | ------------------------------- |
| `oauth.clientId` | The OAuth client id to be used by *Graph UI*  | `telicent-graph-ui`             |
| `oauth.scopes`   | List of OAuth scopes to be used by *Graph UI* | `openid profile offline_access` |

### ConfigMap Parameters

| Name                          | Description                                                 | Value |
| ----------------------------- | ----------------------------------------------------------- | ----- |
| `configMap.existingConfigMap` | The name of an existing config map containing env-config.js | `""`  |

### Common Parameters

| Name                | Description                                                            | Value |
| ------------------- | ---------------------------------------------------------------------- | ----- |
| `nameOverride`      | String to partially override fullname (will maintain the release name) | `""`  |
| `fullnameOverride`  | String to fully override the generated release name                    | `""`  |
| `namespaceOverride` | String to fully override all deployed resources namespace              | `""`  |
| `commonLabels`      | Add labels to all the deployed resources                               | `{}`  |

### Deployment Parameters

| Name                   | Description                                                     | Value |
| ---------------------- | --------------------------------------------------------------- | ----- |
| `replicas`             | Number of *Graph UI* replicas to deploy                         | `1`   |
| `revisionHistoryLimit` | Number of controller revisions to keep                          | `5`   |
| `annotations`          | Add extra annotations to the deployment object                  | `{}`  |
| `podLabels`            | Add extra labels to the *Graph UI* pod                          | `{}`  |
| `podAnnotations`       | Add extra annotations to the *Graph UI* pod                     | `{}`  |
| `extraEnvVars`         | Array with extra environment variables to add to *Graph UI* pod | `[]`  |
| `extraVolumes`         | Optionally specify extra list of additional volumes             | `[]`  |
| `extraVolumeMounts`    | Optionally specify extra list of additional volumeMounts        | `[]`  |
| `initContainers`       | Add init containers to the pod                                  | `[]`  |
| `sidecars`             | Add sidecars to the pod                                         | `[]`  |

### Deployment Image Parameters

| Name                | Description                                                               | Value                     |
| ------------------- | ------------------------------------------------------------------------- | ------------------------- |
| `image.registry`    | *Graph UI* image registry                                                 | `quay.io`                 |
| `image.repository`  | *Graph UI* image name                                                     | `telicent/telicent-graph` |
| `image.tag`         | *Graph UI* image tag. If not set, a tag is generated using the appVersion | `""`                      |
| `image.pullPolicy`  | *Graph UI* image pull policy                                              | `IfNotPresent`            |
| `image.pullSecrets` | Specify registry secret names as an array                                 | `[]`                      |

### Deployment Resources Parameters - Requests and Limits

| Name        | Description                         | Value |
| ----------- | ----------------------------------- | ----- |
| `resources` | Resources for *Graph UI* containers | `{}`  |

### Deployment Security Context Parameters - Default Security Context

| Name                                                | Description                                                             | Value            |
| --------------------------------------------------- | ----------------------------------------------------------------------- | ---------------- |
| `podSecurityContext.runAsUser`                      | Set the provisioning pod's Security Context runAsUser User ID           | `185`            |
| `podSecurityContext.runAsGroup`                     | Set the provisioning pod's Security Context runAsGroup Group ID         | `185`            |
| `podSecurityContext.runAsNonRoot`                   | Set the provisioning pod's Security Context runAsNonRoot                | `true`           |
| `podSecurityContext.fsGroup`                        | Set the provisioning pod's Group ID for the mounted volumes' filesystem | `185`            |
| `podSecurityContext.seccompProfile.type`            | Set the provisioning pod's Security Context seccomp profile             | `RuntimeDefault` |
| `containerSecurityContext.runAsUser`                | Set containers' Security Context runAsUser User ID                      | `185`            |
| `containerSecurityContext.runAsGroup`               | Set containers' Security Context runAsGroup Group ID                    | `185`            |
| `containerSecurityContext.runAsNonRoot`             | Set container's Security Context runAsNonRoot                           | `true`           |
| `containerSecurityContext.allowPrivilegeEscalation` | Set container's Security Context allowPrivilegeEscalation               | `false`          |
| `containerSecurityContext.capabilities.drop`        | List of capabilities to be dropped                                      | `["ALL"]`        |
| `containerSecurityContext.seccompProfile.type`      | Set container's Security Context seccomp profile                        | `RuntimeDefault` |

### Deployment Affinity Parameters

| Name           | Description                    | Value |
| -------------- | ------------------------------ | ----- |
| `affinity`     | Affinity for pod assignment    | `{}`  |
| `nodeSelector` | Node labels for pod assignment | `{}`  |
| `tolerations`  | Tolerations for pod assignment | `[]`  |

### Service Account Parameters

| Name                         | Description                                                                           | Value  |
| ---------------------------- | ------------------------------------------------------------------------------------- | ------ |
| `serviceAccount.create`      | Specifies whether a service account should be created                                 | `true` |
| `serviceAccount.name`        | Name of the ServiceAccount to use. If not set, a name is generated using the fullname | `""`   |
| `serviceAccount.annotations` | Additional custom annotations for the ServiceAccount                                  | `{}`   |
| `serviceAccount.automount`   | Automatically mount a ServiceAccount's API credentials                                | `true` |

### Traffic Exposure Parameters

| Name           | Description                                                                 | Value       |
| -------------- | --------------------------------------------------------------------------- | ----------- |
| `service.name` | *Graph UI* service name. If not set, a name is generated using the fullname | `""`        |
| `service.port` | *Graph UI* service port                                                     | `8080`      |
| `service.type` | *Graph UI* service type                                                     | `ClusterIP` |

### Host(s) Parameters - Contains host information for applications deployed via *telicent-core* chart.

*Graph UI* interacts directly with other Telicent Applications using their default service/serviceAccount and port.
If either of those details changes, you can use this section to correctly refer to those applications.

| Name                      | Description                                                                                                                                                                                                                          | Value                |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------- |
| `hosts.enableAutoCorrect` | Allow for the release name to be automatically pre-fixed to each host value when required (default behavior when installing through the parent chart). Alternatively, the host value will be used as it is, without any modification | `true`               |
| `hosts.traefikProxy`      | Traefik Proxy application default host value, as defined by 'service/serviceAccount:port'                                                                                                                                            | `traefik-proxy:8080` |
