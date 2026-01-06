import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';

interface File {
  id: number;
  repository_id: number;
  commit_id: number;
  path: string;
  language: string | null;
  size_bytes: number;
  line_count: number | null;
}

export default function Files() {
  const { repositoryId } = useParams<{ repositoryId: string }>();
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterLanguage, setFilterLanguage] = useState<string>('');

  useEffect(() => {
    if (repositoryId) {
      fetchFiles();
    }
  }, [repositoryId]);

  const fetchFiles = async () => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/repositories/${repositoryId}/files`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch files');
      }
      const data = await response.json();
      setFiles(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getLanguageBadgeColor = (language: string | null): string => {
    if (!language) return 'bg-gray-100 text-gray-800';

    const colors: Record<string, string> = {
      python: 'bg-blue-100 text-blue-800',
      javascript: 'bg-yellow-100 text-yellow-800',
      typescript: 'bg-blue-100 text-blue-800',
      java: 'bg-red-100 text-red-800',
      go: 'bg-cyan-100 text-cyan-800',
      rust: 'bg-orange-100 text-orange-800',
      c: 'bg-gray-100 text-gray-800',
      cpp: 'bg-purple-100 text-purple-800',
      markdown: 'bg-green-100 text-green-800',
    };

    return colors[language.toLowerCase()] || 'bg-gray-100 text-gray-800';
  };

  // Get unique languages for filter
  const languages = Array.from(
    new Set(files.map((f) => f.language).filter(Boolean))
  ).sort();

  // Filter files
  const filteredFiles = files.filter((file) => {
    const matchesSearch = file.path
      .toLowerCase()
      .includes(searchTerm.toLowerCase());
    const matchesLanguage =
      !filterLanguage || file.language === filterLanguage;
    return matchesSearch && matchesLanguage;
  });

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <p className="text-gray-600">Loading files...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          Error: {error}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <Link
          to="/repositories"
          className="text-blue-600 hover:text-blue-800 mb-4 inline-flex items-center gap-2"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back to Repositories
        </Link>
        <h1 className="text-3xl font-bold text-gray-900">Files</h1>
        <p className="text-gray-600 mt-2">
          {filteredFiles.length} {filteredFiles.length === 1 ? 'file' : 'files'}
          {searchTerm && ` matching "${searchTerm}"`}
        </p>
      </div>

      {/* Filters */}
      <div className="mb-6 flex gap-4">
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search files..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <select
            value={filterLanguage}
            onChange={(e) => setFilterLanguage(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Languages</option>
            {languages.map((lang) => (
              <option key={lang} value={lang || ''}>
                {lang || 'Unknown'}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Files Table */}
      {filteredFiles.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">
            {searchTerm || filterLanguage
              ? 'No files match your filters'
              : 'No files found'}
          </p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Path
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Language
                </th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Size
                </th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Lines
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredFiles.map((file) => (
                <tr
                  key={file.id}
                  className="hover:bg-gray-50 transition-colors"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <svg
                        className="w-4 h-4 text-gray-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                        />
                      </svg>
                      <span className="text-sm text-gray-900 font-mono">
                        {file.path}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {file.language ? (
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getLanguageBadgeColor(
                          file.language
                        )}`}
                      >
                        {file.language}
                      </span>
                    ) : (
                      <span className="text-sm text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-gray-600">
                    {formatFileSize(file.size_bytes)}
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-gray-600">
                    {file.line_count ? file.line_count.toLocaleString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
