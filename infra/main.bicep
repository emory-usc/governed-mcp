// Governed MCP — minimal, scale-to-zero Container Apps deployment.
//
// The server is stateless (no database, no secrets), so this is intentionally
// leaner than a full data-plane deployment. Caller identity is expected to come
// from a token in production (GOVERNED_AUTH_MODE=token), typically injected by
// an auth layer in front of the app — see docs/architecture.md.
//
// Deploy:
//   az deployment group create --resource-group <rg> \
//     --template-file infra/main.bicep --parameters containerImage=<image>

@description('Azure region')
param location string = 'westus3'

@description('Lowercase alphanumeric prefix for resource names')
param namePrefix string = 'governedmcp'

@description('Container image to deploy (e.g. ghcr.io/<user>/governed-mcp:latest)')
param containerImage string

// ---------------------------------------------------------------------------
// Observability
// ---------------------------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${namePrefix}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-appi'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ---------------------------------------------------------------------------
// Managed identity (reserved for token-mode auth / future Entra integration)
// ---------------------------------------------------------------------------
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-identity'
  location: location
}

// ---------------------------------------------------------------------------
// Container Apps environment + app
// ---------------------------------------------------------------------------
resource containerEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${namePrefix}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${namePrefix}-app'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'  // HTTP/1.1 — MCP streamable-http uses SSE
      }
    }
    template: {
      containers: [
        {
          name: 'governed-mcp'
          image: containerImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
          ]
          probes: [
            {
              type: 'Liveness'
              tcpSocket: { port: 8000 }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
}

output appUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
