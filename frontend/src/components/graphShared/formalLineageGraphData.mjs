function fieldEdgeId(edge) {
  return `${edge.sourceAssetCode}.${edge.sourceField}->${edge.targetAssetCode}.${edge.targetField}`
}

function assetEdgeId(edge) {
  return `${edge.sourceAssetCode}->${edge.targetAssetCode}`
}

function fieldNodeId(assetCode, field) {
  return `${assetCode}.${field}`
}

function addNode(nodes, id, label, data, style) {
  if (!nodes.has(id)) {
    nodes.set(id, {
      id,
      data: { label, ...data },
      style: { labelText: label, ...style },
    })
  }
}

export function formalLineageToGraph(lineage) {
  const nodes = new Map()
  const fieldEdges = lineage?.fieldEdges ?? []
  const assetEdges = lineage?.edges ?? []

  if (fieldEdges.length > 0) {
    fieldEdges.forEach((edge) => {
      const source = fieldNodeId(edge.sourceAssetCode, edge.sourceField)
      const target = fieldNodeId(edge.targetAssetCode, edge.targetField)
      addNode(nodes, source, source, {
        assetCode: edge.sourceAssetCode,
        metadataId: edge.sourceMetadataId,
        field: edge.sourceField,
      }, { fill: '#eff6ff', stroke: '#2563eb' })
      addNode(nodes, target, target, {
        assetCode: edge.targetAssetCode,
        metadataId: edge.targetMetadataId,
        field: edge.targetField,
      }, { fill: '#f8fafc', stroke: '#64748b' })
    })

    return {
      nodes: Array.from(nodes.values()),
      edges: fieldEdges.map((edge) => ({
        id: fieldEdgeId(edge),
        source: fieldNodeId(edge.sourceAssetCode, edge.sourceField),
        target: fieldNodeId(edge.targetAssetCode, edge.targetField),
        data: { edgeKind: 'field', rawEdge: edge },
        style: { labelText: edge.expression || edge.lineageType || 'FIELD' },
      })),
    }
  }

  assetEdges.forEach((edge) => {
    addNode(nodes, edge.sourceAssetCode, edge.sourceAssetCode, {
      assetCode: edge.sourceAssetCode,
      metadataId: edge.sourceMetadataId,
    }, { fill: '#ecfdf5', stroke: '#10b981' })
    addNode(nodes, edge.targetAssetCode, edge.targetAssetCode, {
      assetCode: edge.targetAssetCode,
      metadataId: edge.targetMetadataId,
    }, { fill: '#f8fafc', stroke: '#64748b' })
  })

  return {
    nodes: Array.from(nodes.values()),
    edges: assetEdges.map((edge) => ({
      id: assetEdgeId(edge),
      source: edge.sourceAssetCode,
      target: edge.targetAssetCode,
      data: { edgeKind: 'asset', rawEdge: edge },
      style: { labelText: edge.expression || edge.lineageType || 'TABLE' },
    })),
  }
}
