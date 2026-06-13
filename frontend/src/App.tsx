import {
  ApiOutlined,
  ApartmentOutlined,
  BranchesOutlined,
  CommentOutlined,
  DatabaseOutlined,
  HeartOutlined,
  HistoryOutlined,
} from '@ant-design/icons'
import { Badge, Input, Layout, Menu, Space, Typography } from 'antd'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Chat from './pages/Chat'
import Health from './pages/Health'
import Lineage from './pages/Lineage'
import Metadata from './pages/Metadata'
import Pipeline from './pages/Pipeline'
import SchemaEvolution from './pages/SchemaEvolution'

const { Header, Sider, Content } = Layout

const navItems = [
  { key: '/metadata', icon: <DatabaseOutlined />, label: <Link to="/metadata">元数据</Link> },
  { key: '/metadata/lineage', icon: <BranchesOutlined />, label: <Link to="/metadata/lineage">血缘图</Link> },
  { key: '/chat', icon: <CommentOutlined />, label: <Link to="/chat">NL 对话</Link> },
  { key: '/pipeline', icon: <ApartmentOutlined />, label: <Link to="/pipeline">Pipeline</Link> },
  { key: '/schema-evolution', icon: <HistoryOutlined />, label: <Link to="/schema-evolution">演化历史</Link> },
  { key: '/health', icon: <HeartOutlined />, label: <Link to="/health">健康检查</Link> },
]

function selectedKey(pathname: string) {
  if (pathname.startsWith('/metadata/lineage')) return '/metadata/lineage'
  return navItems.find((item) => pathname.startsWith(item.key))?.key ?? '/metadata'
}

export default function App() {
  const location = useLocation()

  return (
    <Layout className="app-shell">
      <Sider className="app-sider" width={232}>
        <div className="brand">
          <ApiOutlined />
          <div>
            <Typography.Text className="brand-title">RNO Data Gov</Typography.Text>
            <Typography.Text className="brand-subtitle">无线数据治理台</Typography.Text>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey(location.pathname)]}
          items={navItems}
          className="side-menu"
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Input.Search
            className="global-search"
            placeholder="搜索表名、字段、描述"
            allowClear
            onSearch={(value) => {
              if (value.trim()) window.location.href = `/metadata?search=${encodeURIComponent(value.trim())}`
            }}
          />
          <Space size={16}>
            <Badge status="processing" text="FastAPI :8000" />
            <Badge status="processing" text="Governance :8080" />
            <Badge status="success" text="Neo4j metadata" />
          </Space>
        </Header>
        <Content className="app-content">
          <Routes>
            <Route path="/" element={<Navigate to="/metadata" replace />} />
            <Route path="/metadata" element={<Metadata />} />
            <Route path="/metadata/lineage" element={<Lineage />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/schema-evolution" element={<SchemaEvolution />} />
            <Route path="/health" element={<Health />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}
