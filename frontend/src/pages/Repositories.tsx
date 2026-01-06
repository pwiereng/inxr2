import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

interface Repository {
  id: number;
  name: string;
  url: string;
  description: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export default function Repositories() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRepositories();
  }, []);

  const fetchRepositories = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/repositories');
      if (!response.ok) {
        throw new Error('Failed to fetch repositories');
      }
      const data = await response.json();
      setRepositories(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <p className="text-gray-600">Loading repositories...</p>
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
        <h1 className="text-3xl font-bold text-gray-900">Repositories</h1>
        <p className="text-gray-600 mt-2">
          Browse indexed code repositories
        </p>
      </div>

      {repositories.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600 mb-4">No repositories indexed yet.</p>
          <p className="text-sm text-gray-500">
            Use the API to index a local directory:
          </p>
          <pre className="mt-4 bg-gray-800 text-gray-100 p-4 rounded text-left text-sm overflow-x-auto">
{`curl -X POST http://localhost:8000/api/index/local \\
  -H "Content-Type: application/json" \\
  -d '{"path": "/workspace", "name": "inxr2"}'`}
          </pre>
        </div>
      ) : (
        <div className="grid gap-4">
          {repositories.map((repo) => (
            <Link
              key={repo.id}
              to={`/repositories/${repo.id}/files`}
              className="block bg-white border border-gray-200 rounded-lg p-6 hover:border-blue-500 hover:shadow-md transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h2 className="text-xl font-semibold text-gray-900 mb-2">
                    {repo.name}
                  </h2>
                  {repo.description && (
                    <p className="text-gray-600 mb-3">{repo.description}</p>
                  )}
                  <div className="flex items-center gap-4 text-sm text-gray-500">
                    <span className="flex items-center gap-1">
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
                          d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                        />
                      </svg>
                      {repo.url}
                    </span>
                    {repo.created_at && (
                      <span className="flex items-center gap-1">
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
                            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                        Indexed {new Date(repo.created_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
                <svg
                  className="w-6 h-6 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
