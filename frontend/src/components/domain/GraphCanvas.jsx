import { useEffect, useRef, useCallback } from 'react'
import cytoscape from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { buildCyElements } from '../../lib/graph/buildCyElements.js'
import './domain.css'

cytoscape.use(fcose)

export function GraphCanvas({
  graph,
  scoresByPath,
  selectedFilePath,
  onSelectNode,
  highlightMode,
  searchQuery,
  minCriticality,
  focusFile,
}) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)

  const applyHighlights = useCallback(
    (cy, mode, selected) => {
      cy.elements().removeClass('dimmed highlighted target')

      if (!selected) {
        return
      }

      const node = cy.getElementById(selected)
      if (!node.length) {
        return
      }

      node.addClass('target')

      if (mode === 'dependencies') {
        const closed = node.outgoers().add(node)
        cy.elements().not(closed).addClass('dimmed')
        closed.addClass('highlighted')
      } else if (mode === 'dependents') {
        const closed = node.incomers().add(node)
        cy.elements().not(closed).addClass('dimmed')
        closed.addClass('highlighted')
      } else if (mode === 'focus') {
        const neighborhood = node.closedNeighborhood()
        cy.elements().not(neighborhood).addClass('dimmed')
        neighborhood.addClass('highlighted')
      }
    },
    [],
  )

  useEffect(() => {
    if (!containerRef.current || !graph) {
      return undefined
    }

    const elements = buildCyElements(graph, scoresByPath)
    const filtered = elements.filter((el) => {
      if (!el.data.criticality && el.data.criticality !== 0) {
        return true
      }
      return el.data.criticality >= minCriticality
    })

    const cy = cytoscape({
      container: containerRef.current,
      elements: filtered,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'background-color': 'data(color)',
            width: 'mapData(criticality, 0, 1, 28, 56)',
            height: 'mapData(criticality, 0, 1, 28, 56)',
            'font-size': 10,
            color: '#2F3E46',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'border-width': 2,
            'border-color': '#fff',
          },
        },
        {
          selector: 'node.target',
          style: {
            'border-color': '#52796F',
            'border-width': 3,
          },
        },
        {
          selector: 'node.highlighted',
          style: {
            opacity: 1,
          },
        },
        {
          selector: 'node.dimmed',
          style: {
            opacity: 0.15,
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1,
            'line-color': '#CAD2C5',
            'target-arrow-color': '#CAD2C5',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            opacity: 0.6,
          },
        },
        {
          selector: 'edge.dimmed',
          style: {
            opacity: 0.08,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#52796F',
          },
        },
      ],
      layout: {
        name: 'fcose',
        animate: true,
        animationDuration: 500,
        nodeDimensionsIncludeLabels: true,
        idealEdgeLength: 80,
        nodeRepulsion: 4500,
      },
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.3,
    })

    cy.on('tap', 'node', (event) => {
      const path = event.target.data('fullPath')
      onSelectNode?.(path)
    })

    cy.on('mouseover', 'node', (event) => {
      const data = event.target.data()
      event.target.style('z-index', 10)
      containerRef.current?.setAttribute(
        'title',
        `${data.fullPath}\nCriticality: ${data.criticality?.toFixed(4) ?? '—'}\nIn: ${data.inDegree} · Out: ${data.outDegree}`,
      )
    })

    cyRef.current = cy

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [graph, scoresByPath, minCriticality, onSelectNode])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) {
      return
    }
    applyHighlights(cy, highlightMode, selectedFilePath)
  }, [highlightMode, selectedFilePath, applyHighlights])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy || !searchQuery) {
      return
    }

    const query = searchQuery.toLowerCase()
    cy.nodes().forEach((node) => {
      const path = node.data('fullPath')?.toLowerCase() ?? ''
      if (path.includes(query)) {
        node.removeClass('dimmed')
        node.addClass('highlighted')
      } else {
        node.addClass('dimmed')
        node.removeClass('highlighted')
      }
    })
  }, [searchQuery])

  useEffect(() => {
    const cy = cyRef.current
    const file = focusFile || selectedFilePath
    if (!cy || !file) {
      return
    }

    const node = cy.getElementById(file)
    if (node.length) {
      cy.animate({
        center: { eles: node },
        zoom: 1.5,
        duration: 300,
      })
      node.select()
    }
  }, [focusFile, selectedFilePath])

  return (
    <div
      className="graph-canvas"
      ref={containerRef}
      role="img"
      aria-label={`Dependency graph with ${graph?.nodes?.length ?? 0} files and ${graph?.edges?.length ?? 0} import relationships`}
    />
  )
}
